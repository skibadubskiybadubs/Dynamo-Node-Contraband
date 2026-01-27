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
        string requestId, TaskCompletionSource<PipeResponse> completion)
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

            if (!alreadyOpen)
            {
                // Open the graph from file
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

            // Subscribe to completion BEFORE triggering Run
            EventHandler<EvaluationCompletedEventArgs>? handler = null;
            handler = (sender, e) =>
            {
                workspace.EvaluationCompleted -= handler;
                try
                {
                    // Step 1: Read event args safely
                    bool? tookPlace = null;
                    bool? succeeded = null;
                    string? evalError = null;
                    try { tookPlace = e.EvaluationTookPlace; } catch { }
                    try { succeeded = e.EvaluationSucceeded; } catch { }
                    try { evalError = e.Error?.Message; } catch { }

                    // Step 2: Capture node outputs
                    List<Dictionary<string, object?>> nodeOutputs;
                    try
                    {
                        nodeOutputs = CaptureNodeOutputs(workspace);
                    }
                    catch (Exception captureEx)
                    {
                        completion.SetResult(PipeResponse.Ok(requestId, "execute",
                            new Dictionary<string, object?>
                            {
                                ["graph_path"] = graphPath,
                                ["already_open"] = alreadyOpen,
                                ["evaluation_took_place"] = tookPlace,
                                ["evaluation_succeeded"] = succeeded,
                                ["capture_error"] = $"{captureEx.GetType().Name}: {captureEx.Message}",
                                ["capture_stack"] = captureEx.StackTrace?.Substring(0, Math.Min(500, captureEx.StackTrace.Length)),
                                ["node_count"] = 0,
                                ["nodes"] = new List<Dictionary<string, object?>>()
                            }));
                        return;
                    }

                    completion.SetResult(PipeResponse.Ok(requestId, "execute",
                        new Dictionary<string, object?>
                        {
                            ["graph_path"] = graphPath,
                            ["already_open"] = alreadyOpen,
                            ["evaluation_took_place"] = tookPlace,
                            ["evaluation_succeeded"] = succeeded,
                            ["evaluation_error"] = evalError,
                            ["node_count"] = nodeOutputs.Count,
                            ["nodes"] = nodeOutputs
                        }));
                }
                catch (Exception ex)
                {
                    completion.TrySetResult(PipeResponse.Fail(requestId, "execute",
                        $"Handler error: {ex.GetType().Name}: {ex.Message}"));
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
