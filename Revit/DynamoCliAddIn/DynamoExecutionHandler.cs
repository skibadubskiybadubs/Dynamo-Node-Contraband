using System.Collections.Concurrent;
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
                var response = ProcessRequest(pending.Request, app);
                pending.Completion.SetResult(response);
            }
            catch (Exception ex)
            {
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
            "execute" => HandleExecute(request, app),
            _ => PipeResponse.Fail(request.Id, request.Command,
                $"Unknown command: {request.Command}")
        };
    }

    private PipeResponse HandlePing(PipeRequest request, UIApplication app)
    {
        var doc = app.ActiveUIDocument?.Document;
        return PipeResponse.Ok(request.Id, "ping", new Dictionary<string, object?>
        {
            ["message"] = "pong",
            ["revit_version"] = app.Application.VersionNumber,
            ["document_name"] = doc?.Title,
            ["dynamo_loaded"] = false // Session 2: detect DynamoRevit
        });
    }

    private PipeResponse HandleStatus(PipeRequest request, UIApplication app)
    {
        var doc = app.ActiveUIDocument?.Document;
        return PipeResponse.Ok(request.Id, "status", new Dictionary<string, object?>
        {
            ["revit_version"] = app.Application.VersionNumber,
            ["document_open"] = doc != null,
            ["document_name"] = doc?.Title,
            ["document_path"] = doc?.PathName,
            ["dynamo_loaded"] = false // Session 2: detect DynamoRevit
        });
    }

    private PipeResponse HandleExecute(PipeRequest request, UIApplication app)
    {
        // Stub for Session 2
        return PipeResponse.Fail(request.Id, "execute",
            "NOT_IMPLEMENTED: Graph execution will be implemented in Session 2.");
    }

    private sealed record PendingRequest(PipeRequest Request, TaskCompletionSource<PipeResponse> Completion);
}
