#!/usr/bin/env python
"""Tool 3: Node Connector - Connect nodes in a Dynamo graph.

Usage:
    dynamo-node-connect graph.dyn --from <output-port-guid> --to <input-port-guid>
    dynamo-node-connect graph.dyn --disconnect <connector-guid>
    dynamo-node-connect graph.dyn --list-ports <node-guid>
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.graph_io import load_graph, save_graph
from tools.common.models import Connector


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


@click.command()
@click.argument("graph_path", type=click.Path(exists=True))
@click.option("--from", "from_port", help="Source output port GUID")
@click.option("--to", "to_port", help="Target input port GUID")
@click.option("--disconnect", "disconnect_id", help="Connector GUID to disconnect")
@click.option("--list-ports", "list_ports_node", help="List ports for a node GUID")
def main(graph_path: str, from_port: Optional[str], to_port: Optional[str],
         disconnect_id: Optional[str], list_ports_node: Optional[str]):
    """Connect or disconnect nodes in a Dynamo graph.

    GRAPH_PATH: Path to the .dyn file to modify.
    """
    try:
        graph = load_graph(graph_path)

        # List ports for a node
        if list_ports_node:
            node = graph.get_node(list_ports_node)
            if not node:
                output_result({"success": False, "error": f"Node not found: {list_ports_node}"})
                sys.exit(1)

            output_result({
                "success": True,
                "node_id": node.Id,
                "node_type": node.NodeType,
                "input_ports": [{"id": p.Id, "name": p.Name} for p in node.Inputs],
                "output_ports": [{"id": p.Id, "name": p.Name} for p in node.Outputs]
            })
            return

        # Disconnect
        if disconnect_id:
            removed = graph.remove_connector(disconnect_id)
            if not removed:
                output_result({"success": False, "error": f"Connector not found: {disconnect_id}"})
                sys.exit(1)

            save_graph(graph, graph_path)
            output_result({
                "success": True,
                "action": "disconnected",
                "connector_id": disconnect_id
            })
            return

        # Connect
        if from_port and to_port:
            # Validate ports exist
            from_node = graph.find_port_owner(from_port)
            to_node = graph.find_port_owner(to_port)

            if not from_node:
                output_result({"success": False, "error": f"Source port not found: {from_port}"})
                sys.exit(1)

            if not to_node:
                output_result({"success": False, "error": f"Target port not found: {to_port}"})
                sys.exit(1)

            # Verify from_port is an output and to_port is an input
            from_is_output = any(p.Id == from_port for p in from_node.Outputs)
            to_is_input = any(p.Id == to_port for p in to_node.Inputs)

            if not from_is_output:
                output_result({
                    "success": False,
                    "error": f"Port {from_port} is not an output port. Use --list-ports to see available ports."
                })
                sys.exit(1)

            if not to_is_input:
                output_result({
                    "success": False,
                    "error": f"Port {to_port} is not an input port. Use --list-ports to see available ports."
                })
                sys.exit(1)

            # Check if connection already exists
            for c in graph.Connectors:
                if c.Start == from_port and c.End == to_port:
                    output_result({
                        "success": False,
                        "error": f"Connection already exists with id: {c.Id}"
                    })
                    sys.exit(1)

            # Create connector
            connector = Connector.create(from_port, to_port)
            graph.add_connector(connector)

            save_graph(graph, graph_path)
            output_result({
                "success": True,
                "action": "connected",
                "connector_id": connector.Id,
                "from_port": from_port,
                "from_node": from_node.Id,
                "to_port": to_port,
                "to_node": to_node.Id
            })
            return

        # No valid operation specified
        output_result({
            "success": False,
            "error": "Specify --from and --to to connect, --disconnect to remove, or --list-ports to inspect"
        })
        sys.exit(1)

    except FileNotFoundError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
