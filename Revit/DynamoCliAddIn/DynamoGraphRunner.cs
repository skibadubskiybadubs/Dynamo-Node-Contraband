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
    private const int EvalTimeoutMs = 120_000;

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
    /// Execute a .dyn graph and return node outputs.
    /// Must be called on the Revit main thread (inside IExternalEventHandler.Execute).
    /// </summary>
    public static GraphExecutionResult Execute(DynamoModel model, string graphPath)
    {
        if (!File.Exists(graphPath))
            return GraphExecutionResult.Error($"Graph file not found: {graphPath}");

        try
        {
            // Open the graph (forceManualExecutionMode: true to prevent auto-run)
            model.OpenFileFromPath(graphPath, forceManualExecutionMode: true);

            var workspace = model.CurrentWorkspace as HomeWorkspaceModel;
            if (workspace == null)
                return GraphExecutionResult.Error("Failed to open graph as HomeWorkspaceModel.");

            // Set up completion wait
            using var completionEvent = new ManualResetEventSlim(false);
            bool evaluationSucceeded = false;
            string? evalError = null;

            void OnEvalCompleted(object? sender, EvaluationCompletedEventArgs e)
            {
                evaluationSucceeded = e.EvaluationSucceeded;
                if (e.Error != null) evalError = e.Error.Message;
                completionEvent.Set();
            }

            workspace.EvaluationCompleted += OnEvalCompleted;
            try
            {
                // Trigger execution
                workspace.Run();

                // Wait for completion
                if (!completionEvent.Wait(EvalTimeoutMs))
                    return GraphExecutionResult.Error($"Graph execution timed out after {EvalTimeoutMs / 1000}s.");
            }
            finally
            {
                workspace.EvaluationCompleted -= OnEvalCompleted;
            }

            if (!evaluationSucceeded)
                return GraphExecutionResult.Error($"Graph evaluation failed: {evalError ?? "unknown error"}");

            // Capture outputs from all nodes
            var nodeOutputs = CaptureNodeOutputs(workspace);
            return GraphExecutionResult.Success(nodeOutputs);
        }
        catch (Exception ex)
        {
            return GraphExecutionResult.Error($"Graph execution error: {ex.Message}");
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

/// <summary>
/// Result of graph execution containing node outputs or error info.
/// </summary>
public sealed class GraphExecutionResult
{
    public bool IsSuccess { get; private init; }
    public string? ErrorMessage { get; private init; }
    public List<Dictionary<string, object?>>? NodeOutputs { get; private init; }

    public static GraphExecutionResult Success(List<Dictionary<string, object?>> outputs) =>
        new() { IsSuccess = true, NodeOutputs = outputs };

    public static GraphExecutionResult Error(string message) =>
        new() { IsSuccess = false, ErrorMessage = message };
}
