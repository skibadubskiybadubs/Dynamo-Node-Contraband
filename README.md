# Dynamo Node Contraband

CLI tools for autonomous AI agents to create and manipulate Dynamo Python Node graphs.

## Tools

| Tool | Command | Purpose |
|------|---------|---------|
| Graph Init | `dynamo-graph-init` | Create new empty graph or clear existing |
| Graph Reader | `dynamo-graph-read` | Inspect graph structure, list nodes/connections |
| Node Creator | `dynamo-node-create` | Create Python, Number, String nodes |
| Node Connector | `dynamo-node-connect` | Connect nodes via port GUIDs |
| Code Injector | `dynamo-code-inject` | Inject/update Python code in nodes |
| Graph Executor | `dynamo-execute` | Execute graph via DynamoCLI |
| Output Reader | `dynamo-output-read` | Parse XML output, extract results |

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

### Automatic Setup (Recommended)

The configurator tool detects installed Dynamo environments, manages profiles, and fixes known dependency issues.

**1. Detect installations and save profiles:**

```bash
python -m tools.common.configurate_dynamo detect --save
```

This scans for Dynamo Sandbox (`.sandboxed/`) and DynamoForRevit (`C:\Program Files\Autodesk\Revit {year}\AddIns\DynamoForRevit\`) installations. Each one is saved as a named profile in `config/dynamo.yaml` (e.g. `sandbox`, `revit_2025`). The tool also detects the .NET framework (net48 for Revit 2024, net8.0 for Revit 2025+) and infers the Python engine accordingly.

**2. Switch between environments:**

```bash
python -m tools.common.configurate_dynamo switch revit_2025
python -m tools.common.configurate_dynamo switch revit_2024
python -m tools.common.configurate_dynamo switch sandbox
```

This updates `dynamo.cli_path`, `dynamo.version`, and `dynamo.engine` in the config file so all other tools use the selected environment.

**3. Validate an environment:**

```bash
python -m tools.common.configurate_dynamo validate
python -m tools.common.configurate_dynamo validate --profile revit_2025
```

Runs three health checks: CLI executable exists, critical DLLs are present, and the CLI starts without assembly loading errors.

**4. Fix missing dependencies:**

DynamoForRevit installations ship without `System.Configuration.ConfigurationManager.dll`, a dependency DynamoCLI needs at startup. The Sandbox installation *does* include it. The `fix` command copies this DLL from `.sandboxed/` into the target DynamoForRevit directory.

```bash
# Preview what will be copied
python -m tools.common.configurate_dynamo fix --profile revit_2025 --dry-run

# Apply the fix (requires administrator shell for Program Files paths)
python -m tools.common.configurate_dynamo fix --profile revit_2025
```

**5. Show current config:**

```bash
python -m tools.common.configurate_dynamo show
```

### Manual Configuration (Fallback)

If the configurator tool doesn't work, edit `config/dynamo.yaml` directly:

```yaml
dynamo:
  cli_path: "C:\\Program Files\\Autodesk\\Revit 2025\\AddIns\\DynamoForRevit\\DynamoCLI.exe"
  version: "3.3"
  engine: "CPython3"
  default_timeout: 300
```

If DynamoForRevit fails with an assembly loading error, manually copy `System.Configuration.ConfigurationManager.dll` from `.sandboxed\` into the DynamoForRevit directory.

## Use with Revit

You can establish connection with running Revit instance by first installing the plugin:
```bash
powershell.exe -ExecutionPolicy Bypass -File "C:\GitHub\Dynamo-Node-Contraband\Revit\DynamoCliAddIn\install.ps1"
```

Then, open Revit project and test the connection:
```bash
python -m tools.dynamo_execute_revit --ping 2>&1
```
Output on success:
```bash
{
  "success": true,
  "command": "ping",
  "data": {
    "message": "pong",                                // Revit responede back to call
    "revit_version": "2025",
    "document_name": "revit_test",
    "dynamo_loaded": false
  }
}
```

Then, open Dynamo project in Revit and test the connection again:
```bash
python -m tools.dynamo_execute_revit --ping
```
Output on success:
```bash
{
  "success": true,
  "command": "ping",
  "data": {
    "message": "pong",
    "revit_version": "2025",
    "document_name": "revit_test",
    "dynamo_loaded": true                             // Detected opened Dynamo graph in Revit
  }
}
```

You can now try to execute the running Dynamo script:
```bash
python -m tools.dynamo_execute_revit tests\revit_test.dyn
```
Output on success:
```bash
{
  "id": "3c094bad-b9cf-4204-8955-8a92e8a73577",
  "success": true,
  "command": "execute",
  "data": {
    "graph_path": "C:\\GitHub\\Dynamo-Node-Contraband\\tests\\revit_test.dyn",
    "already_open": true,                             // 'true' means the graph is currently opened in Dynamo
    "evaluation_took_place": false,                   // 'false' means Dynamo used its cached values from the already-running graph rather than re-evaluating
    "evaluation_succeeded": true,
    "evaluation_error": null,
    "node_count": 3,
    "nodes": [
      {
        "id": "c4b56bfc-d289-4b54-be75-44f1d637624d",
        "name": "Select Model Element",
        "type": "ExtensionNode",
        "state": "Active",
        "value": {
          "_type": "Wall",                            // Selected Revit Elements
          "string": "Wall",
          "id": "1658741",
          "name": "Generic - 200mm"
        }
      },
      {
        "id": "318e5628-3634-46cd-b5e3-90ee9c1821cf",
        "name": "Element By Id",
        "type": "ExtensionNode",
        "state": "Active",
        "value": {
          "_type": "Wall",                            // Selected Revit Elements
          "string": "Wall",
          "id": "1658741",
          "name": "Generic - 200mm"
        }
      },
      {
        "id": "78360635-dbc7-4875-99c1-c73551df6e47",
        "name": "Element.Id",
        "type": "FunctionNode",
        "state": "Active",
        "value": 1658741                              // Selected Revit Elements
      }
    ]
  },
  "error": null
}
```

Now you can access the data from Dynamo graph opened in Revit in real-time.
For example here the graph was in Automatic run mode. 
Another element was selected, but the graph has not been re-saved.
And the tool picked up the new result:
```bash
python -m tools.dynamo_execute_revit tests\revit_test.dyn
{
  "id": "c4c86d84-042f-4a10-a661-3634fe0fd823",
  "success": true,
  "command": "execute",
  "data": {
    "graph_path": "C:\\GitHub\\Dynamo-Node-Contraband\\tests\\revit_test.dyn",
    "already_open": true,
    "evaluation_took_place": false,                   // Still used Dynamo's cached data
    "evaluation_succeeded": true,
    "evaluation_error": null,
    "node_count": 3,
    "nodes": [
      {
        "id": "c4b56bfc-d289-4b54-be75-44f1d637624d",
        "name": "Select Model Element",
        "type": "ExtensionNode",
        "state": "Active",
        "value": {
          "_type": "FamilyInstance",
          "string": "750 x 2000mm",
          "id": "1658821",
          "name": "750 x 2000mm"
        }
      },
      {
        "id": "318e5628-3634-46cd-b5e3-90ee9c1821cf",
        "name": "Element By Id",
        "type": "ExtensionNode",
        "state": "Active",
        "value": {
          "_type": "FamilyInstance",
          "string": "750 x 2000mm",
          "id": "1658821",
          "name": "750 x 2000mm"
        }
      },
      {
        "id": "78360635-dbc7-4875-99c1-c73551df6e47",
        "name": "Element.Id",
        "type": "FunctionNode",
        "state": "Active",
        "value": 1658821                              // New Revit Element withour re-saving Dynamo graph
      }
    ]
  },
  "error": null
}
```

Another test. Now graph in Manual run mode.
Selected new Revit object, didn't re-save or re-run the graph.
```bash
python -m tools.dynamo_execute_revit tests\revit_test.dyn
{
  "id": "42751bdd-93fd-44e2-a653-ac0c1a749737",
  "success": true,
  "command": "execute",
  "data": {
    "graph_path": "C:\\GitHub\\Dynamo-Node-Contraband\\tests\\revit_test.dyn",
    "already_open": true,
    "evaluation_took_place": true,                    // Didn't use Cached data from Dynamo!
    "evaluation_succeeded": true,
    "evaluation_error": null,
    "node_count": 3,
    "nodes": [
      {
        "id": "c4b56bfc-d289-4b54-be75-44f1d637624d",
        "name": "Select Model Element",
        "type": "ExtensionNode",
        "state": "Active",
        "value": {
          "_type": "FamilyInstance",
          "string": "600 x 900mm",
          "id": "1658944",                            // But it didn't pick up the latest selection (still old value)
          "name": "600 x 900mm"
        }
      },
      {
        "id": "318e5628-3634-46cd-b5e3-90ee9c1821cf",
        "name": "Element By Id",
        "type": "ExtensionNode",
        "state": "Active",
        "value": {
          "_type": "FamilyInstance",
          "string": "600 x 900mm",
          "id": "1658944",
          "name": "600 x 900mm"
        }
      },
      {
        "id": "78360635-dbc7-4875-99c1-c73551df6e47",
        "name": "Element.Id",
        "type": "FunctionNode",
        "state": "Active",
        "value": 1658944
      }
    ]
  },
  "error": null
}
```
However, after this command run - it did re-run the graph, and all the nodes in the Graph opened in Dynamo updated their outputs.
And when I re-run the command again - it saccessfully pick up those values:
```bash
python -m tools.dynamo_execute_revit tests\revit_test.dyn
{
  "id": "6458fee1-6042-4a3f-9bde-1a00bf418d11",
  "success": true,
  "command": "execute",
  "data": {
    "graph_path": "C:\\GitHub\\Dynamo-Node-Contraband\\tests\\revit_test.dyn",
    "already_open": true,
    "evaluation_took_place": false,
    "evaluation_succeeded": true,
    "evaluation_error": null,
    "node_count": 3,
    "nodes": [
      {
        "id": "c4b56bfc-d289-4b54-be75-44f1d637624d",
        "name": "Select Model Element",
        "type": "ExtensionNode",
        "state": "Active",
        "value": {
          "_type": "Wall",
          "string": "Wall",
          "id": "1658741",                // The new selection after re-running the command
          "name": "Generic - 200mm"
        }
      },
      {
        "id": "318e5628-3634-46cd-b5e3-90ee9c1821cf",
        "name": "Element By Id",
        "type": "ExtensionNode",
        "state": "Active",
        "value": {
          "_type": "Wall",
          "string": "Wall",
          "id": "1658741",
          "name": "Generic - 200mm"
        }
      },
      {
        "id": "78360635-dbc7-4875-99c1-c73551df6e47",
        "name": "Element.Id",
        "type": "FunctionNode",
        "state": "Active",
        "value": 1658741
      }
    ]
  },
  "error": null
}
```
So I think if the Dynamo graph is in automatic mode, it should return the data after the graph has been run.

## Usage Examples

### Read a graph
```bash
python -m tools.dynamo_graph_read graph.dyn --nodes
```

### Create nodes
```bash
# Create a number input (value=42)
python -m tools.dynamo_node_create graph.dyn number --value 42 --position "50,100"

# Create a Python script node
python -m tools.dynamo_node_create graph.dyn python --name "MyScript" --inputs 2 --position "250,100"
```

### Connect nodes
```bash
# List ports for a node
python -m tools.dynamo_node_connect graph.dyn --list-ports <node-guid>

# Connect output port to input port
python -m tools.dynamo_node_connect graph.dyn --from <output-port-guid> --to <input-port-guid>
```

### Inject Python code
```bash
# Inject inline code
python -m tools.dynamo_code_inject graph.dyn <node-guid> --code "OUT = IN[0] * 2"

# Inject from file
python -m tools.dynamo_code_inject graph.dyn <node-guid> --file script.py

# Read current code
python -m tools.dynamo_code_inject graph.dyn <node-guid> --get
```

### Execute graph
```bash
python -m tools.dynamo_execute graph.dyn --output output.xml --timeout 60
```

### Read execution output
```bash
# All outputs
python -m tools.dynamo_output_read output.xml

# Specific node
python -m tools.dynamo_output_read output.xml --node <node-guid>
```

## Complete Workflow Example

```bash
# 1. Create a new empty graph
python -m tools.dynamo_graph_init tests/my_graph.dyn --name "My Graph"

# Or read an existing graph
python -m tools.dynamo_graph_read tests/graph.dyn

# 2. Create number input (value=5)
python -m tools.dynamo_node_create tests/graph.dyn number --value 5 --position "50,100"
# Returns: node_id, output_ports[0].id

# 3. Create Python node
python -m tools.dynamo_node_create tests/graph.dyn python --name "Doubler" --inputs 1 --position "250,100"
# Returns: node_id, input_ports[0].id, output_ports[0].id

# 4. Connect number output to Python input
python -m tools.dynamo_node_connect tests/graph.dyn --from <number-output-port> --to <python-input-port>

# 5. Inject code
python -m tools.dynamo_code_inject tests/graph.dyn <python-node-id> --code "OUT = IN[0] * 2"

# 6. Execute (requires Dynamo runtime)
python -m tools.dynamo_execute tests/graph.dyn --output output.xml

# 7. Read result
python -m tools.dynamo_output_read output.xml --node <python-node-id>
# Expected: {"outputs": [{"value": 10}]}
```

## Execution Environment

**Important**: Graph execution requires a working Dynamo installation:

- **Dynamo Sandbox** (recommended): Works standalone for headless execution
- **Dynamo for Revit**: Requires Revit to be running with Dynamo loaded

If you see assembly loading errors, ensure you're using the correct CLI for your environment.

## Output Format

All tools output JSON for AI consumption:

```json
{
  "success": true,
  "node_id": "guid",
  "...": "..."
}
```

Errors return:
```json
{
  "success": false,
  "error": "Error message"
}
```

## License

MIT
