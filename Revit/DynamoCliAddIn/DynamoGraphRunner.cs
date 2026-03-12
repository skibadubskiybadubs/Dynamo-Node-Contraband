using System.Reflection;
using Dynamo.Graph.Nodes;
using Dynamo.Graph.Workspaces;
using Dynamo.Models;

namespace DynamoCliAddIn;

/// <summary>
/// Loads and executes Dynamo graphs using the running DynamoRevit model.
/// Accesses the DynamoRevit singleton via reflection since DynamoRevitDS
/// types depend on assemblies only available inside the Revit process.
/// </summary>
public static class DynamoGraphRunner
{
    /// <summary>
    /// Check if DynamoRevit is loaded and return the model if available.
    /// </summary>
    public static DynamoModel? GetDynamoModel()
    {
        try
        {
            var asm = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(a => a.GetName().Name == "DynamoRevitDS");
            if (asm == null) return null;

            var type = asm.GetType("Dynamo.Applications.DynamoRevit");
            if (type == null) return null;

            var prop = type.GetProperty("RevitDynamoModel", BindingFlags.Public | BindingFlags.Static);
            return prop?.GetValue(null) as DynamoModel;
        }
        catch
        {
            return null;
        }
    }

    private const int EvalTimeoutMs = 90_000; // 90s safety timeout for evaluation callback

    /// <summary>
    /// Start graph execution asynchronously. Must be called on the Revit main thread.
    /// Returns immediately - the TCS is completed later by the EvaluationCompleted callback
    /// after the Revit main thread is free to process Dynamo's scheduled work.
    /// </summary>
    public static void ExecuteAsync(DynamoModel model, string graphPath,
        string requestId, TaskCompletionSource<PipeResponse> completion, bool forceReopen = false)
    {
        if (!File.Exists(graphPath))
        {
            completion.SetResult(PipeResponse.Fail(requestId, "execute",
                $"Graph file not found: {graphPath}"));
            return;
        }

        try
        {
            // Check if the graph is already the current workspace
            var currentWs = model.CurrentWorkspace as HomeWorkspaceModel;
            bool alreadyOpen = currentWs != null &&
                string.Equals(currentWs.FileName, graphPath, StringComparison.OrdinalIgnoreCase);

            Logger.Info($"ExecuteAsync: graph={Path.GetFileName(graphPath)} alreadyOpen={alreadyOpen} forceReopen={forceReopen}");

            if (!alreadyOpen || forceReopen)
            {
                model.OpenFileFromPath(graphPath, forceManualExecutionMode: false);
                currentWs = model.CurrentWorkspace as HomeWorkspaceModel;
            }

            if (currentWs == null)
            {
                completion.SetResult(PipeResponse.Fail(requestId, "execute",
                    "Failed to get HomeWorkspaceModel."));
                return;
            }

            var workspace = currentWs;

            // Subscribe to EvaluationCompleted BEFORE triggering Run.
            // The callback fires after Dynamo finishes evaluating all nodes.
            EventHandler<EvaluationCompletedEventArgs>? handler = null;
            handler = (sender, e) =>
            {
                try
                {
                    workspace.EvaluationCompleted -= handler;

                    Logger.Info($"EvaluationCompleted: succeeded={e.EvaluationSucceeded} tookPlace={e.EvaluationTookPlace}");

                    if (!e.EvaluationSucceeded)
                    {
                        var errorMsg = e.Error?.Message ?? "Unknown evaluation error";
                        Logger.Warn($"Graph evaluation failed: {errorMsg}");
                        completion.TrySetResult(PipeResponse.Fail(requestId, "execute",
                            $"Graph evaluation failed. {errorMsg}"));
                        return;
                    }

                    var nodeOutputs = CaptureNodeOutputs(workspace);
                    Logger.Info($"Captured {nodeOutputs.Count} node outputs");
                    completion.TrySetResult(PipeResponse.Ok(requestId, "execute",
                        new Dictionary<string, object?>
                        {
                            ["graph_path"] = graphPath,
                            ["node_count"] = nodeOutputs.Count,
                            ["nodes"] = nodeOutputs
                        }));
                }
                catch (Exception ex)
                {
                    Logger.Error("Output capture error", ex);
                    workspace.EvaluationCompleted -= handler;
                    completion.TrySetResult(PipeResponse.Fail(requestId, "execute",
                        $"Output capture error: {ex.GetType().Name}: {ex.Message}"));
                }
            };

            workspace.EvaluationCompleted += handler;

            // Safety timeout: if EvaluationCompleted never fires, complete with error.
            var timer = new System.Threading.Timer(_ =>
            {
                if (!completion.Task.IsCompleted)
                {
                    workspace.EvaluationCompleted -= handler;
                    Logger.Warn($"Evaluation timeout after {EvalTimeoutMs / 1000}s for {Path.GetFileName(graphPath)}");
                    completion.TrySetResult(PipeResponse.Fail(requestId, "execute",
                        $"Evaluation timeout: Dynamo did not complete within {EvalTimeoutMs / 1000}s."));
                }
            }, null, EvalTimeoutMs, Timeout.Infinite);

            // Dispose timer when TCS completes (by callback or timeout).
            completion.Task.ContinueWith(_ => timer.Dispose());

            // Trigger execution - returns immediately, work is scheduled on the Revit thread.
            workspace.Run();

            // DO NOT WAIT HERE - return to free the Revit main thread.
            // The EvaluationCompleted callback will complete the TCS.
        }
        catch (Exception ex)
        {
            completion.SetResult(PipeResponse.Fail(requestId, "execute",
                $"Graph execution error: {ex.Message}"));
        }
    }

    private static List<Dictionary<string, object?>> CaptureNodeOutputs(HomeWorkspaceModel workspace)
    {
        var results = new List<Dictionary<string, object?>>();

        foreach (var node in workspace.Nodes)
        {
            var nodeResult = new Dictionary<string, object?>
            {
                ["id"] = node.GUID.ToString(),
                ["name"] = node.Name,
                ["type"] = node.NodeType,
                ["state"] = node.State.ToString(),
                ["value"] = ResultSerializer.Serialize(node.CachedValue)
            };
            results.Add(nodeResult);
        }

        return results;
    }
}
