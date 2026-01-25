#!/usr/bin/env python
"""Tool: Graph Init - Create a new empty Dynamo graph.

Usage:
    dynamo-graph-init output.dyn                    # Create new graph
    dynamo-graph-init output.dyn --name "My Graph"  # Create with custom name
    dynamo-graph-init output.dyn --clear            # Clear existing graph
"""

import json
import sys
from pathlib import Path

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.graph_io import create_empty_graph, save_graph, load_graph


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


@click.command()
@click.argument("graph_path", type=click.Path())
@click.option("--name", default="graph", help="Name for the graph")
@click.option("--clear", is_flag=True, help="Clear an existing graph (remove all nodes/connectors)")
@click.option("--force", is_flag=True, help="Overwrite existing file")
def main(graph_path: str, name: str, clear: bool, force: bool):
    """Create a new empty Dynamo graph file.

    GRAPH_PATH: Path for the new .dyn file.
    """
    try:
        path = Path(graph_path)

        # Check if file exists
        if path.exists() and not clear and not force:
            output_result({
                "success": False,
                "error": f"File already exists: {graph_path}. Use --force to overwrite or --clear to empty it."
            })
            sys.exit(1)

        if clear and path.exists():
            # Load existing graph and clear nodes/connectors
            graph = load_graph(graph_path)
            graph.Nodes = []
            graph.Connectors = []
            graph.NodeViews = []
            save_graph(graph, graph_path)

            output_result({
                "success": True,
                "action": "cleared",
                "graph_id": graph.Uuid,
                "name": graph.Name,
                "path": str(path.absolute())
            })
        else:
            # Create new empty graph
            graph = create_empty_graph(name)
            save_graph(graph, graph_path)

            output_result({
                "success": True,
                "action": "created",
                "graph_id": graph.Uuid,
                "name": graph.Name,
                "path": str(path.absolute())
            })

    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
