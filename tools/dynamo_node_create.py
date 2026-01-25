#!/usr/bin/env python
"""Tool 2: Node Creator - Create nodes in a Dynamo graph.

Usage:
    dynamo-node-create graph.dyn python --name "My Script"
    dynamo-node-create graph.dyn python --name "My Script" --inputs 2 --position 100,200
    dynamo-node-create graph.dyn number --value 42 --position 50,100
    dynamo-node-create graph.dyn string --value "Hello" --position 50,150
"""

import json
import sys
from pathlib import Path
from typing import Optional, Tuple

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.config import get_node_template, get_dynamo_engine
from tools.common.graph_io import load_graph, save_graph
from tools.common.models import Node, Port, NodeView, generate_guid


def parse_position(ctx, param, value: Optional[str]) -> Tuple[float, float]:
    """Parse position string like '100,200' into (x, y) tuple."""
    if value is None:
        return (0.0, 0.0)
    try:
        parts = value.split(",")
        if len(parts) != 2:
            raise click.BadParameter("Position must be in format 'x,y' (e.g., '100,200')")
        return (float(parts[0].strip()), float(parts[1].strip()))
    except ValueError:
        raise click.BadParameter("Position values must be numbers")


def create_python_node(name: str, num_inputs: int, position: Tuple[float, float]) -> Tuple[Node, NodeView]:
    """Create a Python Script node."""
    template = get_node_template("python")
    node_id = generate_guid()

    # Create input ports
    inputs = []
    for i in range(num_inputs):
        port = Port.create(f"IN[{i}]", f"Input #{i}")
        inputs.append(port)

    # Create output port
    output = Port.create("OUT", "Result of the python script")

    # Build node
    node = Node(
        Id=node_id,
        NodeType=template["NodeType"],
        ConcreteType=template["ConcreteType"],
        Inputs=inputs,
        Outputs=[output],
        Replication=template.get("Replication", "Disabled"),
        Description=template.get("Description", ""),
        _extra={
            "Code": "# Python code here\nOUT = None",
            "Engine": template.get("Engine", "CPython3"),
            "EngineName": template.get("EngineName", "CPython3"),
            "VariableInputPorts": template.get("VariableInputPorts", True),
        }
    )

    # Create view
    view = NodeView.create(node_id, name or "Python Script", position[0], position[1])

    return node, view


def create_number_node(value: float, position: Tuple[float, float]) -> Tuple[Node, NodeView]:
    """Create a Number Input node."""
    template = get_node_template("number")
    node_id = generate_guid()

    # Create output port
    output = Port.create("", "Double")

    # Build node
    node = Node(
        Id=node_id,
        NodeType=template["NodeType"],
        ConcreteType=template["ConcreteType"],
        Inputs=[],
        Outputs=[output],
        Replication=template.get("Replication", "Disabled"),
        Description=template.get("Description", ""),
        _extra={
            "NumberType": template.get("NumberType", "Double"),
            "InputValue": value,
        }
    )

    # Create view
    view = NodeView.create(node_id, "Number", position[0], position[1])

    return node, view


def create_string_node(value: str, position: Tuple[float, float]) -> Tuple[Node, NodeView]:
    """Create a String Input node."""
    template = get_node_template("string")
    node_id = generate_guid()

    # Create output port
    output = Port.create("", "String")

    # Build node
    node = Node(
        Id=node_id,
        NodeType=template["NodeType"],
        ConcreteType=template["ConcreteType"],
        Inputs=[],
        Outputs=[output],
        Replication=template.get("Replication", "Disabled"),
        Description=template.get("Description", ""),
        _extra={
            "InputValue": value,
        }
    )

    # Create view
    view = NodeView.create(node_id, "String", position[0], position[1])

    return node, view


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


@click.command()
@click.argument("graph_path", type=click.Path(exists=True))
@click.argument("node_type", type=click.Choice(["python", "number", "string"]))
@click.option("--name", help="Name for the node (Python nodes only)")
@click.option("--inputs", "num_inputs", type=int, default=1, help="Number of input ports (Python nodes only)")
@click.option("--value", help="Initial value (Number/String nodes)")
@click.option("--position", callback=parse_position, help="Position as 'x,y' (e.g., '100,200')")
def main(graph_path: str, node_type: str, name: Optional[str], num_inputs: int,
         value: Optional[str], position: Tuple[float, float]):
    """Create a new node in a Dynamo graph.

    GRAPH_PATH: Path to the .dyn file to modify.
    NODE_TYPE: Type of node to create (python, number, string).
    """
    try:
        graph = load_graph(graph_path)

        # Create the appropriate node type
        if node_type == "python":
            node, view = create_python_node(name or "Python Script", num_inputs, position)

        elif node_type == "number":
            try:
                num_value = float(value) if value else 0.0
            except ValueError:
                output_result({"success": False, "error": f"Invalid number value: {value}"})
                sys.exit(1)
            node, view = create_number_node(num_value, position)

        elif node_type == "string":
            str_value = value if value else ""
            node, view = create_string_node(str_value, position)

        else:
            output_result({"success": False, "error": f"Unknown node type: {node_type}"})
            sys.exit(1)

        # Add to graph
        graph.add_node(node, view)

        # Save graph
        save_graph(graph, graph_path)

        # Output result
        output_result({
            "success": True,
            "node_id": node.Id,
            "node_type": node.NodeType,
            "input_ports": [{"id": p.Id, "name": p.Name} for p in node.Inputs],
            "output_ports": [{"id": p.Id, "name": p.Name} for p in node.Outputs],
            "position": {"x": view.X, "y": view.Y}
        })

    except FileNotFoundError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
