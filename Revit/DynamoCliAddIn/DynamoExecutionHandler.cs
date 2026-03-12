using System.Collections.Concurrent;
using System.Text.Json;
using Autodesk.Revit.UI;

namespace DynamoCliAddIn;

/// <summary>
/// Bridges the named pipe server thread to the Revit main thread via ExternalEvent.
/// Pending requests are enqueued from the pipe server thread, and processed
/// when Revit calls Execute() on the main thread.
/// </summary>
public sealed class DynamoExecutionHandler : IExternalEventHandler
{
    private readonly ConcurrentQueue<PendingRequest> _queue = new();

    /// <summary>
    /// Enqueue a request from the pipe server thread. Returns a task that
    /// completes when the request has been processed on the Revit main thread.
    /// </summary>
    public Task<PipeResponse> EnqueueRequest(PipeRequest request)
    {
        var tcs = new TaskCompletionSource<PipeResponse>(TaskCreationOptions.RunContinuationsAsynchronously);
        _queue.Enqueue(new PendingRequest(request, tcs));
        return tcs.Task;
    }

    /// <summary>
    /// Called by Revit on the main thread when ExternalEvent.Raise() is invoked.
    /// Processes all pending requests in the queue.
    /// </summary>
    public void Execute(UIApplication app)
    {
        while (_queue.TryDequeue(out var pending))
        {
            try
            {
                if (pending.Request.Command.Equals("execute", StringComparison.OrdinalIgnoreCase))
                {
                    // Execute commands are async - they start graph execution and return
                    // immediately. The TCS is completed later by the EvaluationCompleted
                    // callback, after the Revit main thread is free to process Dynamo work.
                    HandleExecuteAsync(pending.Request, app, pending.Completion);
                }
                else
                {
                    var response = ProcessRequest(pending.Request, app);
                    pending.Completion.SetResult(response);
                }
            }
            catch (Exception ex)
            {
                Logger.Error($"Handler error for cmd={pending.Request.Command}", ex);
                var errorResponse = PipeResponse.Fail(
                    pending.Request.Id,
                    pending.Request.Command,
                    $"Revit handler error: {ex.Message}");
                pending.Completion.SetResult(errorResponse);
            }
        }
    }

    public string GetName() => "DynamoCliAddIn.DynamoExecutionHandler";

    private PipeResponse ProcessRequest(PipeRequest request, UIApplication app)
    {
        return request.Command.ToLowerInvariant() switch
        {
            "ping" => HandlePing(request, app),
            "status" => HandleStatus(request, app),
            _ => PipeResponse.Fail(request.Id, request.Command,
                $"Unknown command: {request.Command}")
        };
    }

    private PipeResponse HandlePing(PipeRequest request, UIApplication app)
    {
        var doc = app.ActiveUIDocument?.Document;
        var dynamoModel = DynamoGraphRunner.GetDynamoModel();
        return PipeResponse.Ok(request.Id, "ping", new Dictionary<string, object?>
        {
            ["message"] = "pong",
            ["revit_version"] = app.Application.VersionNumber,
            ["document_name"] = doc?.Title,
            ["dynamo_loaded"] = dynamoModel != null
        });
    }

    private PipeResponse HandleStatus(PipeRequest request, UIApplication app)
    {
        var doc = app.ActiveUIDocument?.Document;
        var dynamoModel = DynamoGraphRunner.GetDynamoModel();
        return PipeResponse.Ok(request.Id, "status", new Dictionary<string, object?>
        {
            ["revit_version"] = app.Application.VersionNumber,
            ["document_open"] = doc != null,
            ["document_name"] = doc?.Title,
            ["document_path"] = doc?.PathName,
            ["dynamo_loaded"] = dynamoModel != null
        });
    }

    private void HandleExecuteAsync(PipeRequest request, UIApplication app,
        TaskCompletionSource<PipeResponse> completion)
    {
        // Extract graph_path from payload
        string? graphPath = null;
        bool reload = false;

        if (request.Payload != null)
        {
            if (request.Payload.TryGetValue("graph_path", out var pathObj))
            {
                if (pathObj is JsonElement jsonEl)
                    graphPath = jsonEl.GetString();
                else
                    graphPath = pathObj?.ToString();
            }

            if (request.Payload.TryGetValue("reload", out var reloadObj))
            {
                if (reloadObj is JsonElement jsonEl)
                    reload = jsonEl.GetBoolean();
                else if (reloadObj is bool b)
                    reload = b;
            }
        }

        if (string.IsNullOrWhiteSpace(graphPath))
        {
            completion.SetResult(PipeResponse.Fail(request.Id, "execute",
                "Missing 'graph_path' in payload."));
            return;
        }

        // Check Dynamo is loaded
        var dynamoModel = DynamoGraphRunner.GetDynamoModel();
        if (dynamoModel == null)
        {
            completion.SetResult(PipeResponse.Fail(request.Id, "execute",
                "DYNAMO_NOT_LOADED: Open Dynamo in Revit before executing graphs."));
            return;
        }

        // Start async execution - TCS will be completed by EvaluationCompleted callback
        DynamoGraphRunner.ExecuteAsync(dynamoModel, graphPath, request.Id, completion, forceReopen: reload);
    }

    private sealed record PendingRequest(PipeRequest Request, TaskCompletionSource<PipeResponse> Completion);
}
