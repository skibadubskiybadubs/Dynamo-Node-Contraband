using System.Text.Json.Serialization;

namespace DynamoCliAddIn;

/// <summary>
/// JSON request received from the Python CLI client.
/// </summary>
public sealed class PipeRequest
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("command")]
    public string Command { get; set; } = string.Empty;

    [JsonPropertyName("payload")]
    public Dictionary<string, object>? Payload { get; set; }
}

/// <summary>
/// JSON response sent back to the Python CLI client.
/// </summary>
public sealed class PipeResponse
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("command")]
    public string Command { get; set; } = string.Empty;

    [JsonPropertyName("data")]
    public Dictionary<string, object?>? Data { get; set; }

    [JsonPropertyName("error")]
    public string? Error { get; set; }

    public static PipeResponse Ok(string id, string command, Dictionary<string, object?> data) =>
        new() { Id = id, Success = true, Command = command, Data = data };

    public static PipeResponse Fail(string id, string command, string error) =>
        new() { Id = id, Success = false, Command = command, Error = error };
}
