using System.Collections.Concurrent;

namespace DynamoCliAddIn;

/// <summary>
/// Simple file-based logger for diagnosing add-in issues.
/// Writes timestamped entries to %USERPROFILE%/DynamoCliAddIn.log.
/// Thread-safe: queues messages and writes from a background thread.
/// </summary>
public static class Logger
{
    private static readonly string LogPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "DynamoCliAddIn.log");
    private static readonly BlockingCollection<string> Queue = new(1024);
    private static readonly Thread WriterThread;

    static Logger()
    {
        WriterThread = new Thread(WriteLoop)
        {
            IsBackground = true,
            Name = "DynamoCliAddIn.Logger"
        };
        WriterThread.Start();
    }

    public static void Info(string message) => Enqueue("INFO", message);
    public static void Warn(string message) => Enqueue("WARN", message);
    public static void Error(string message) => Enqueue("ERROR", message);

    public static void Error(string message, Exception ex) =>
        Enqueue("ERROR", $"{message} | {ex.GetType().Name}: {ex.Message}");

    private static void Enqueue(string level, string message)
    {
        var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff} [{level}] {message}";
        Queue.TryAdd(line);
    }

    private static void WriteLoop()
    {
        try
        {
            using var writer = new StreamWriter(LogPath, append: true) { AutoFlush = true };
            foreach (var line in Queue.GetConsumingEnumerable())
            {
                writer.WriteLine(line);
            }
        }
        catch
        {
            // Logger must never crash the host process
        }
    }
}
