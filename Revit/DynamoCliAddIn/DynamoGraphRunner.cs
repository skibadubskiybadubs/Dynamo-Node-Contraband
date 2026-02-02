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

            if (!alreadyOpen || forceReopen)
            {
                // Open the graph from file (force reload from disk if requested)
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

            // Subscribe to completion BEFORE triggering Run.
            // When evaluation_took_place is true, CachedValues may not be settled yet.
            // Re-trigger Run() to get a second callback where values are finalized.
            EventHandler<EvaluationCompletedEventArgs>? handler = null;
            handler = (sender, e) =>
            {
                try
                {
                    if (e.EvaluationTookPlace)
                    {
                        // Values not settled yet - keep subscription and re-run.
                        // Second callback will have took_place=false with correct CachedValues.
                        workspace.Run();
                        return;
                    }

                    // Values are settled - capture outputs
                    workspace.EvaluationCompleted -= handler;

                    var nodeOutputs = CaptureNodeOutputs(workspace);
                    completion.TrySetResult(PipeResponse.Ok(requestId, "execute",
                        new Dictionary<string, object?>
                        {
                            ["graph_path"] = graphPath,
                            ["already_open"] = alreadyOpen,
                            ["node_count"] = nodeOutputs.Count,
                            ["nodes"] = nodeOutputs
                        }));
                }
                catch (Exception ex)
                {
                    workspace.EvaluationCompleted -= handler;
                    completion.TrySetResult(PipeResponse.Fail(requestId, "execute",
                        $"Output capture error: {ex.GetType().Name}: {ex.Message}"));
                }
            };

            workspace.EvaluationCompleted += handler;

            // Trigger execution - returns immediately, work is scheduled
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
