using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using Autodesk.Revit.UI;

namespace DynamoCliAddIn;

/// <summary>
/// Named pipe server that listens for JSON requests from Python CLI tools.
/// Runs on a background thread and forwards requests to the Revit main thread
/// via ExternalEvent + DynamoExecutionHandler.
/// </summary>
public sealed class PipeServer : IDisposable
{
    public const string PipeName = "DynamoCliAddIn";
    private const int TimeoutMs = 120_000;

    private readonly DynamoExecutionHandler _handler;
    private readonly ExternalEvent _externalEvent;
    private readonly CancellationTokenSource _cts = new();
    private Thread? _thread;

    public PipeServer(DynamoExecutionHandler handler, ExternalEvent externalEvent)
    {
        _handler = handler;
        _externalEvent = externalEvent;
    }

    /// <summary>
    /// Start the pipe server on a background thread.
    /// </summary>
    public void Start()
    {
        _thread = new Thread(ServerLoop)
        {
            IsBackground = true,
            Name = "DynamoCliAddIn.PipeServer"
        };
        _thread.Start();
    }

    /// <summary>
    /// Stop the pipe server and release resources.
    /// </summary>
    public void Dispose()
    {
        _cts.Cancel();
        _thread = null;
    }

    private void ServerLoop()
    {
        while (!_cts.IsCancellationRequested)
        {
            NamedPipeServerStream? pipe = null;
            try
            {
                pipe = new NamedPipeServerStream(
                    PipeName,
                    PipeDirection.InOut,
                    NamedPipeServerStream.MaxAllowedServerInstances,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous);

                // Wait for a client connection (blocking, but cancellable)
                try
                {
                    pipe.WaitForConnectionAsync(_cts.Token).GetAwaiter().GetResult();
                }
                catch (OperationCanceledException)
                {
                    pipe.Dispose();
                    break;
                }

                HandleConnection(pipe);
            }
            catch (Exception ex)
            {
                if (_cts.IsCancellationRequested) break;
                Logger.Error("Pipe server error, retrying in 500ms", ex);
                Thread.Sleep(500);
            }
            finally
            {
                pipe?.Dispose();
            }
        }
    }

    private void HandleConnection(NamedPipeServerStream pipe)
    {
        try
        {
            // Read the request line
            using var reader = new StreamReader(pipe, Encoding.UTF8, leaveOpen: true);
            var line = reader.ReadLine();
            if (string.IsNullOrWhiteSpace(line)) return;

            PipeRequest? request;
            try
            {
                request = JsonSerializer.Deserialize<PipeRequest>(line);
            }
            catch (JsonException ex)
            {
                WriteResponse(pipe, PipeResponse.Fail("", "unknown", $"Invalid JSON: {ex.Message}"));
                return;
            }

            if (request == null)
            {
                WriteResponse(pipe, PipeResponse.Fail("", "unknown", "Null request"));
                return;
            }

            Logger.Info($"Request: cmd={request.Command} id={request.Id}");

            // Enqueue request for the Revit main thread
            var responseTask = _handler.EnqueueRequest(request);
            _externalEvent.Raise();

            // Wait for the response with timeout
            if (!responseTask.Wait(TimeoutMs))
            {
                Logger.Warn($"Timeout after {TimeoutMs / 1000}s: cmd={request.Command} id={request.Id}");
                WriteResponse(pipe, PipeResponse.Fail(request.Id, request.Command,
                    $"Timeout: Revit did not process the request within {TimeoutMs / 1000}s. " +
                    "Revit may be busy with a modal dialog or long-running operation."));
                return;
            }

            Logger.Info($"Response: cmd={request.Command} success={responseTask.Result.Success}");
            WriteResponse(pipe, responseTask.Result);
        }
        catch (Exception ex)
        {
            try
            {
                WriteResponse(pipe, PipeResponse.Fail("", "unknown", $"Server error: {ex.Message}"));
            }
            catch
            {
                // Client disconnected, ignore
            }
        }
    }

    private static void WriteResponse(NamedPipeServerStream pipe, PipeResponse response)
    {
        var json = JsonSerializer.Serialize(response);
        var bytes = Encoding.UTF8.GetBytes(json + "\n");
        pipe.Write(bytes, 0, bytes.Length);
        pipe.Flush();
    }
}
