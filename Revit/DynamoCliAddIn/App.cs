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
            var handler = new DynamoExecutionHandler();
            _externalEvent = ExternalEvent.Create(handler);
            _pipeServer = new PipeServer(handler, _externalEvent);
            _pipeServer.Start();
            return Result.Succeeded;
        }
        catch (Exception)
        {
            return Result.Failed;
        }
    }

    public Result OnShutdown(UIControlledApplication application)
    {
        _pipeServer?.Dispose();
        _externalEvent?.Dispose();
        return Result.Succeeded;
    }
}
