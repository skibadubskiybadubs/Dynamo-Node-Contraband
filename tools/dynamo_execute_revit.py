#!/usr/bin/env python
"""Tool 7: Revit Graph Executor - Execute Dynamo graphs via Revit IPC.

Connects to the DynamoCliAddIn named pipe server running inside Revit 2025
to execute graphs with full access to the Revit model context.

Usage:
    dynamo-execute-revit --ping                  # Test connection to Revit
    dynamo-execute-revit --status                # Get Revit state info
    dynamo-execute-revit graph.dyn               # Execute graph in Revit
    dynamo-execute-revit graph.dyn --timeout 60  # Custom timeout
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.ipc_client import (
    IpcConnectionError,
    IpcError,
    IpcTimeoutError,
    execute_graph,
    get_status,
    is_available,
    ping,
)


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


@click.command()
@click.argument("graph_path", required=False, type=click.Path())
@click.option("--ping", "do_ping", is_flag=True, help="Test connection to Revit")
@click.option("--status", "do_status", is_flag=True, help="Get Revit status")
@click.option("--timeout", type=int, default=120, help="Timeout in seconds")
@click.option("--reload", is_flag=True, help="Force reload of graph from disk")
def main(graph_path: Optional[str], do_ping: bool, do_status: bool, timeout: int, reload: bool):
    """Execute a Dynamo graph via the Revit IPC bridge.

    GRAPH_PATH: Path to the .dyn file to execute (optional if using --ping or --status).
    """
    try:
        if do_ping:
            result = ping(timeout=timeout)
            output_result({"success": True, "command": "ping", "data": result})
            return

        if do_status:
            result = get_status(timeout=timeout)
            output_result({"success": True, "command": "status", "data": result})
            return

        if not graph_path:
            click.echo("Error: Provide a GRAPH_PATH or use --ping / --status.", err=True)
            sys.exit(1)

        # Resolve to absolute path
        graph_path = os.path.abspath(graph_path)
        if not os.path.exists(graph_path):
            output_result({"success": False, "error": f"Graph not found: {graph_path}"})
            sys.exit(1)

        result = execute_graph(graph_path, timeout=timeout, reload=reload)
        output_result(result)
        if not result.get("success"):
            sys.exit(1)

    except IpcConnectionError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except IpcTimeoutError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except IpcError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
