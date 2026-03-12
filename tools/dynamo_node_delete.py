#!/usr/bin/env python
"""Tool 8: Node Deleter - Remove nodes from a Dynamo graph.

Usage:
    dynamo-node-delete graph.dyn <node-guid>
    dynamo-node-delete graph.dyn --name "My Script"
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.graph_io import load_graph, save_graph


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


@click.command()
@click.argument("graph_path", type=click.Path(exists=True))
@click.argument("node_id", required=False, default=None)
@click.option("--name", "node_name", help="Delete node by name")
def main(graph_path: str, node_id: Optional[str], node_name: Optional[str]):
    """Delete a node from a Dynamo graph.

    GRAPH_PATH: Path to the .dyn file to modify.
    NODE_ID: GUID of the node to delete (optional if --name is used).
    """
    try:
        graph = load_graph(graph_path)

        if not node_id and not node_name:
            output_result({"success": False, "error": "Provide NODE_ID or --name"})
            sys.exit(1)

        if node_id and node_name:
            output_result({"success": False, "error": "Provide NODE_ID or --name, not both"})
            sys.exit(1)

        # Resolve by name
        if node_name:
            try:
                node = graph.get_node_by_name(node_name)
            except ValueError as e:
                output_result({"success": False, "error": str(e)})
                sys.exit(1)
            if not node:
                output_result({"success": False, "error": f"Node not found by name: {node_name}"})
                sys.exit(1)
            node_id = node.Id
        else:
            node = graph.get_node(node_id)
            if not node:
                output_result({"success": False, "error": f"Node not found: {node_id}"})
                sys.exit(1)

        # Count connectors before removal
        connectors_before = len(graph.Connectors)

        # Get node info for response
        view = graph.get_node_view(node_id)
        node_info = {
            "id": node.Id,
            "type": node.NodeType,
            "name": view.Name if view else "",
        }

        # Remove node (also removes associated connectors and view)
        graph.remove_node(node_id)

        connectors_removed = connectors_before - len(graph.Connectors)

        # Save graph
        save_graph(graph, graph_path)

        output_result({
            "success": True,
            "deleted_node": node_info,
            "connectors_removed": connectors_removed,
            "remaining_nodes": len(graph.Nodes),
        })

    except FileNotFoundError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
