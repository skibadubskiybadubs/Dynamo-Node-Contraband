using ProtoCore.Mirror;

namespace DynamoCliAddIn;

/// <summary>
/// Converts MirrorData from Dynamo node outputs into JSON-serializable objects.
/// </summary>
public static class ResultSerializer
{
    /// <summary>
    /// Convert a MirrorData value to a JSON-safe object.
    /// </summary>
    public static object? Serialize(MirrorData? mirror)
    {
        if (mirror == null || mirror.IsNull)
            return null;

        if (mirror.IsCollection)
        {
            var elements = mirror.GetElements();
            return elements.Select(Serialize).ToList();
        }

        // Try to extract the raw data
        try
        {
            var data = mirror.Data;

            if (data == null)
                return mirror.StringData;

            // Primitives pass through directly
            if (data is bool or int or long or float or double or string)
                return data;

            // For Revit elements, try to extract useful info via reflection
            var dataType = data.GetType();
            var typeName = dataType.FullName ?? dataType.Name;

            if (typeName.Contains("Revit") || typeName.Contains("Element"))
            {
                return SerializeRevitElement(data, dataType, mirror);
            }

            // Fallback: use StringData
            return mirror.StringData;
        }
        catch
        {
            // Last resort fallback
            return mirror.StringData;
        }
    }

    private static Dictionary<string, object?> SerializeRevitElement(
        object data, Type dataType, MirrorData mirror)
    {
        var result = new Dictionary<string, object?>
        {
            ["_type"] = dataType.Name,
            ["string"] = mirror.StringData
        };

        // Try to get Id property
        try
        {
            var idProp = dataType.GetProperty("Id");
            if (idProp != null)
            {
                var idVal = idProp.GetValue(data);
                // Revit 2025 uses int64 ElementId
                result["id"] = idVal?.ToString();
            }
        }
        catch { /* ignore */ }

        // Try to get Name property
        try
        {
            var nameProp = dataType.GetProperty("Name");
            if (nameProp != null)
                result["name"] = nameProp.GetValue(data)?.ToString();
        }
        catch { /* ignore */ }

        // Try to get Category
        try
        {
            var catProp = dataType.GetProperty("Category");
            if (catProp != null)
            {
                var cat = catProp.GetValue(data);
                if (cat != null)
                {
                    var catNameProp = cat.GetType().GetProperty("Name");
                    result["category"] = catNameProp?.GetValue(cat)?.ToString();
                }
            }
        }
        catch { /* ignore */ }

        return result;
    }
}
