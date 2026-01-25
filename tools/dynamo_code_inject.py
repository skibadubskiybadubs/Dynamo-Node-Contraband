#!/usr/bin/env python
"""Tool 4: Code Injector - Inject Python code into Python Script nodes.

Usage:
    dynamo-code-inject graph.dyn <node-guid> --code "OUT = IN[0] * 2"
    dynamo-code-inject graph.dyn <node-guid> --file script.py
    dynamo-code-inject graph.dyn <node-guid> --get
"""

import ast
import json
import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.graph_io import load_graph, save_graph


def validate_python_syntax(code: str) -> tuple[bool, Optional[str]]:
    """Validate Python syntax.

    Returns:
        Tuple of (is_valid, error_message).
    """
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


@click.command()
@click.argument("graph_path", type=click.Path(exists=True))
@click.argument("node_id")
@click.option("--code", help="Python code to inject (inline)")
@click.option("--file", "code_file", type=click.Path(exists=True), help="Python file to inject")
@click.option("--get", "get_code", is_flag=True, help="Get current code from node")
@click.option("--no-validate", is_flag=True, help="Skip syntax validation")
def main(graph_path: str, node_id: str, code: Optional[str], code_file: Optional[str],
         get_code: bool, no_validate: bool):
    """Inject or retrieve Python code in a Python Script node.

    GRAPH_PATH: Path to the .dyn file to modify.
    NODE_ID: GUID of the Python Script node.
    """
    try:
        graph = load_graph(graph_path)

        # Find the node
        node = graph.get_node(node_id)
        if not node:
            output_result({"success": False, "error": f"Node not found: {node_id}"})
            sys.exit(1)

        # Verify it's a Python node
        if not node.is_python_node:
            output_result({
                "success": False,
                "error": f"Node is not a Python Script node (type: {node.NodeType})"
            })
            sys.exit(1)

        # Get current code
        if get_code:
            current_code = node.code or ""
            output_result({
                "success": True,
                "node_id": node_id,
                "code": current_code,
                "code_length": len(current_code)
            })
            return

        # Determine code to inject
        if code_file:
            with open(code_file, "r", encoding="utf-8") as f:
                inject_code = f.read()
        elif code:
            inject_code = code
        else:
            output_result({
                "success": False,
                "error": "Specify --code or --file to inject, or --get to retrieve code"
            })
            sys.exit(1)

        # Validate syntax
        syntax_valid = True
        syntax_error = None
        if not no_validate:
            syntax_valid, syntax_error = validate_python_syntax(inject_code)
            if not syntax_valid:
                output_result({
                    "success": False,
                    "error": f"Python syntax error: {syntax_error}",
                    "code_preview": inject_code[:200] + "..." if len(inject_code) > 200 else inject_code
                })
                sys.exit(1)

        # Inject code
        node.code = inject_code

        # Save graph
        save_graph(graph, graph_path)

        output_result({
            "success": True,
            "node_id": node_id,
            "code_length": len(inject_code),
            "syntax_valid": syntax_valid
        })

    except FileNotFoundError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
