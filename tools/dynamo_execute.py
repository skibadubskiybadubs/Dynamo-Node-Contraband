#!/usr/bin/env python
"""Tool 5: Graph Executor - Execute Dynamo graphs via DynamoCLI.

Usage:
    dynamo-execute graph.dyn                        # Execute, return status
    dynamo-execute graph.dyn --output output.xml    # Execute with verbose output
    dynamo-execute graph.dyn --timeout 60           # Custom timeout in seconds
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.config import get_dynamo_cli_path, get_default_timeout


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


def execute_graph(graph_path: str, output_xml: Optional[str] = None,
                  timeout: int = 300) -> dict:
    """Execute a Dynamo graph via DynamoCLI.

    Args:
        graph_path: Path to the .dyn file.
        output_xml: Optional path for verbose XML output.
        timeout: Timeout in seconds.

    Returns:
        Dict with execution results.
    """
    cli_path = get_dynamo_cli_path()

    # Verify CLI exists
    if not os.path.exists(cli_path):
        return {
            "success": False,
            "error": f"DynamoCLI not found at: {cli_path}"
        }

    # Build command
    graph_path = os.path.abspath(graph_path)
    cmd = [cli_path, "-o", graph_path]

    if output_xml:
        output_xml = os.path.abspath(output_xml)
        cmd.extend(["-v", output_xml])

    # Execute
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(cli_path)  # Run from CLI directory
        )
        execution_time_ms = int((time.time() - start_time) * 1000)

        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "execution_time_ms": execution_time_ms,
            "output_xml": output_xml if output_xml and os.path.exists(output_xml) else None,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except subprocess.TimeoutExpired:
        execution_time_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "error": f"Execution timed out after {timeout} seconds",
            "exit_code": -1,
            "execution_time_ms": execution_time_ms,
            "output_xml": None,
            "stdout": "",
            "stderr": ""
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution failed: {str(e)}",
            "exit_code": -1,
            "execution_time_ms": 0,
            "output_xml": None,
            "stdout": "",
            "stderr": ""
        }


@click.command()
@click.argument("graph_path", type=click.Path(exists=True))
@click.option("--output", "output_xml", help="Path for verbose XML output")
@click.option("--timeout", type=int, default=None, help="Timeout in seconds")
def main(graph_path: str, output_xml: Optional[str], timeout: Optional[int]):
    """Execute a Dynamo graph via DynamoCLI.

    GRAPH_PATH: Path to the .dyn file to execute.
    """
    try:
        # Use default timeout if not specified
        if timeout is None:
            timeout = get_default_timeout()

        # Auto-generate output path if not specified but verbose output is desired
        if output_xml is None:
            # Create output directory if needed
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            # Generate output filename
            graph_name = Path(graph_path).stem
            output_xml = str(output_dir / f"{graph_name}_output.xml")

        result = execute_graph(graph_path, output_xml, timeout)
        output_result(result)

        if not result.get("success", False):
            sys.exit(1)

    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
