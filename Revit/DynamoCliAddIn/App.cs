using Autodesk.Revit.UI;

namespace DynamoCliAddIn;

/// <summary>
/// Revit external application entry point.
/// Creates the ExternalEvent and starts the named pipe IPC server
/// so that Python CLI tools can communicate with the running Revit process.
/// </summary>
public class App : IExternalApplication
{
    private PipeServer? _pipeServer;
    private ExternalEvent? _externalEvent;

    public Result OnStartup(UIControlledApplication application)
    {
        try
        {
            Logger.Info("=== DynamoCliAddIn starting ===");
            var handler = new DynamoExecutionHandler();
            _externalEvent = ExternalEvent.Create(handler);
            _pipeServer = new PipeServer(handler, _externalEvent);
            _pipeServer.Start();
            Logger.Info("Pipe server started on \\\\.\\pipe\\DynamoCliAddIn");
            return Result.Succeeded;
        }
        catch (Exception ex)
        {
            Logger.Error("Startup failed", ex);
            return Result.Failed;
        }
    }

    public Result OnShutdown(UIControlledApplication application)
    {
        Logger.Info("=== DynamoCliAddIn shutting down ===");
        _pipeServer?.Dispose();
        _externalEvent?.Dispose();
        return Result.Succeeded;
    }
}
