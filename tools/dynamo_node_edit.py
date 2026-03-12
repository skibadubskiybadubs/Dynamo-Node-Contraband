#!/usr/bin/env python
"""Tool 9: Node Editor - Edit node ports, values, and names.

Usage:
    dynamo-node-edit graph.dyn <node-guid> --add-input
    dynamo-node-edit graph.dyn --name "Script" --remove-input 1
    dynamo-node-edit graph.dyn --name "Number" --set-value 42
    dynamo-node-edit graph.dyn --name "Script" --rename "Doubler"
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.graph_io import load_graph, save_graph
from tools.common.models import Port


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


@click.command()
@click.argument("graph_path", type=click.Path(exists=True))
@click.argument("node_id", required=False, default=None)
@click.option("--name", "node_name", help="Find node by name")
@click.option("--add-input", is_flag=True, help="Add a new input port")
@click.option("--remove-input", type=int, default=None, help="Remove input port by index")
@click.option("--set-value", default=None, help="Set the node's InputValue")
@click.option("--rename", default=None, help="Rename the node (NodeView.Name)")
def main(graph_path: str, node_id: Optional[str], node_name: Optional[str],
         add_input: bool, remove_input: Optional[int], set_value: Optional[str],
         rename: Optional[str]):
    """Edit a node's ports, value, or name.

    GRAPH_PATH: Path to the .dyn file to modify.
    NODE_ID: GUID of the node (optional if --name is used).
    """
    try:
        graph = load_graph(graph_path)

        if not node_id and not node_name:
            output_result({"success": False, "error": "Provide NODE_ID or --name"})
            sys.exit(1)

        if node_id and node_name:
            output_result({"success": False, "error": "Provide NODE_ID or --name, not both"})
            sys.exit(1)

        # Resolve node
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

        actions = []

        # --add-input
        if add_input:
            if not node._extra.get("VariableInputPorts"):
                output_result({
                    "success": False,
                    "error": f"Node type '{node.NodeType}' does not support variable input ports"
                })
                sys.exit(1)
            idx = len(node.Inputs)
            port = Port.create(f"IN[{idx}]", f"Input #{idx}")
            node.Inputs.append(port)
            actions.append({"action": "add_input", "port_id": port.Id, "port_name": port.Name})

        # --remove-input
        if remove_input is not None:
            if remove_input < 0 or remove_input >= len(node.Inputs):
                output_result({
                    "success": False,
                    "error": f"Input index {remove_input} out of range (node has {len(node.Inputs)} inputs)"
                })
                sys.exit(1)
            removed_port = node.Inputs.pop(remove_input)
            # Remove connectors to this port
            graph.Connectors = [c for c in graph.Connectors
                                if c.Start != removed_port.Id and c.End != removed_port.Id]
            # Re-index remaining input ports
            for i, port in enumerate(node.Inputs):
                port.Name = f"IN[{i}]"
                port.Description = f"Input #{i}"
            actions.append({"action": "remove_input", "removed_port_id": removed_port.Id, "removed_index": remove_input})

        # --set-value
        if set_value is not None:
            if node.NodeType == "NumberInputNode":
                try:
                    node._extra["InputValue"] = float(set_value)
                except ValueError:
                    output_result({"success": False, "error": f"Invalid number value: {set_value}"})
                    sys.exit(1)
            else:
                node._extra["InputValue"] = set_value
            actions.append({"action": "set_value", "value": node._extra["InputValue"]})

        # --rename
        if rename is not None:
            view = graph.get_node_view(node_id)
            if view:
                old_name = view.Name
                view.Name = rename
                actions.append({"action": "rename", "old_name": old_name, "new_name": rename})
            else:
                output_result({"success": False, "error": f"NodeView not found for node {node_id}"})
                sys.exit(1)

        if not actions:
            output_result({
                "success": False,
                "error": "No edit operation specified. Use --add-input, --remove-input, --set-value, or --rename."
            })
            sys.exit(1)

        # Save graph
        save_graph(graph, graph_path)

        output_result({
            "success": True,
            "node_id": node_id,
            "actions": actions,
            "input_count": len(node.Inputs),
        })

    except FileNotFoundError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
