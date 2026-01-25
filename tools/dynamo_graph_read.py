#!/usr/bin/env python
"""Tool 1: Graph Reader - Inspect Dynamo graph structure.

Usage:
    dynamo-graph-read graph.dyn                     # Show summary
    dynamo-graph-read graph.dyn --nodes             # List all nodes
    dynamo-graph-read graph.dyn --node <guid>       # Show specific node
    dynamo-graph-read graph.dyn --connectors        # List all connections
    dynamo-graph-read graph.dyn --json              # Output as JSON (default)
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.graph_io import load_graph
from tools.common.models import Graph, Node


def node_summary(node: Node) -> dict:
    """Create a summary dict for a node."""
    summary = {
        "id": node.Id,
        "type": node.NodeType,
        "concrete_type": node.ConcreteType,
        "input_count": len(node.Inputs),
        "output_count": len(node.Outputs),
        "input_ports": [{"id": p.Id, "name": p.Name} for p in node.Inputs],
        "output_ports": [{"id": p.Id, "name": p.Name} for p in node.Outputs],
    }

    # Add type-specific info
    if node.is_python_node:
        summary["code_length"] = len(node.code) if node.code else 0
    if "InputValue" in node._extra:
        summary["value"] = node._extra["InputValue"]

    return summary


def node_detail(node: Node, graph: Graph) -> dict:
    """Create a detailed dict for a node."""
    detail = node_summary(node)

    # Add code for Python nodes
    if node.is_python_node and node.code:
        detail["code"] = node.code

    # Add position from NodeView
    view = graph.get_node_view(node.Id)
    if view:
        detail["position"] = {"x": view.X, "y": view.Y}
        detail["name"] = view.Name

    # Add connections
    connections = graph.get_connections_for_node(node.Id)
    detail["connections"] = [
        {"id": c.Id, "from": c.Start, "to": c.End}
        for c in connections
    ]

    return detail


def output_result(data: dict, as_json: bool = True):
    """Output result to stdout."""
    if as_json:
        click.echo(json.dumps(data, indent=2))
    else:
        # Simple text output
        for key, value in data.items():
            click.echo(f"{key}: {value}")


@click.command()
@click.argument("graph_path", type=click.Path(exists=True))
@click.option("--nodes", is_flag=True, help="List all nodes with GUIDs")
@click.option("--node", "node_id", help="Show specific node details by GUID")
@click.option("--connectors", is_flag=True, help="List all connections")
@click.option("--json", "as_json", is_flag=True, default=True, help="Output as JSON (default)")
def main(graph_path: str, nodes: bool, node_id: Optional[str], connectors: bool, as_json: bool):
    """Read and inspect a Dynamo graph file.

    GRAPH_PATH: Path to the .dyn file to read.
    """
    try:
        graph = load_graph(graph_path)

        # Show specific node
        if node_id:
            node = graph.get_node(node_id)
            if not node:
                output_result({
                    "success": False,
                    "error": f"Node not found: {node_id}"
                })
                sys.exit(1)

            output_result({
                "success": True,
                "node": node_detail(node, graph)
            })
            return

        # List all nodes
        if nodes:
            output_result({
                "success": True,
                "node_count": len(graph.Nodes),
                "nodes": [node_summary(n) for n in graph.Nodes]
            })
            return

        # List connectors
        if connectors:
            connector_list = []
            for c in graph.Connectors:
                conn_info = {
                    "id": c.Id,
                    "from_port": c.Start,
                    "to_port": c.End,
                }
                # Find owning nodes
                from_node = graph.find_port_owner(c.Start)
                to_node = graph.find_port_owner(c.End)
                if from_node:
                    conn_info["from_node"] = from_node.Id
                if to_node:
                    conn_info["to_node"] = to_node.Id
                connector_list.append(conn_info)

            output_result({
                "success": True,
                "connector_count": len(graph.Connectors),
                "connectors": connector_list
            })
            return

        # Default: show summary
        output_result({
            "success": True,
            "graph_id": graph.Uuid,
            "name": graph.Name,
            "node_count": len(graph.Nodes),
            "connector_count": len(graph.Connectors),
            "nodes": [
                {
                    "id": n.Id,
                    "type": n.NodeType,
                    "inputs": len(n.Inputs),
                    "outputs": len(n.Outputs)
                }
                for n in graph.Nodes
            ]
        })

    except FileNotFoundError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except json.JSONDecodeError as e:
        output_result({"success": False, "error": f"Invalid JSON in graph file: {e}"})
        sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
