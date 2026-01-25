"""Graph I/O utilities for loading and saving .dyn files."""

import json
from pathlib import Path
from typing import Union

from .models import Graph, Node, Connector, NodeView


def load_graph(path: Union[str, Path]) -> Graph:
    """Load a Dynamo graph from a .dyn file.

    Args:
        path: Path to the .dyn file.

    Returns:
        Graph object with all nodes, connectors, and views.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Graph file not found: {path}")

    if path.suffix.lower() != ".dyn":
        raise ValueError(f"Expected .dyn file, got: {path.suffix}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Parse nodes
    nodes = [Node.from_dict(n) for n in data.get("Nodes", [])]

    # Parse connectors
    connectors = [Connector.from_dict(c) for c in data.get("Connectors", [])]

    # Parse node views from View section
    view_data = data.get("View", {})
    node_views = [NodeView.from_dict(nv) for nv in view_data.get("NodeViews", [])]

    return Graph(
        Uuid=data.get("Uuid", ""),
        Name=data.get("Name", ""),
        Nodes=nodes,
        Connectors=connectors,
        NodeViews=node_views,
        _raw=data
    )


def save_graph(graph: Graph, path: Union[str, Path]):
    """Save a Dynamo graph to a .dyn file.

    This preserves all original data from the loaded file,
    only updating the Nodes, Connectors, and NodeViews.

    Args:
        graph: Graph object to save.
        path: Path to save to.
    """
    path = Path(path)

    # Start with original raw data to preserve unknown fields
    data = graph._raw.copy() if graph._raw else {}

    # Update core fields
    data["Uuid"] = graph.Uuid
    data["Name"] = graph.Name
    data["Nodes"] = [n.to_dict() for n in graph.Nodes]
    data["Connectors"] = [c.to_dict() for c in graph.Connectors]

    # Update View.NodeViews
    if "View" not in data:
        data["View"] = {}
    data["View"]["NodeViews"] = [nv.to_dict() for nv in graph.NodeViews]

    # Ensure other View defaults exist
    view = data["View"]
    view.setdefault("Dynamo", {
        "ScaleFactor": 1.0,
        "HasRunWithoutCrash": True,
        "IsVisibleInDynamoLibrary": True,
        "Version": "3.3.0.6316",
        "RunType": "Automatic",
        "RunPeriod": "1000"
    })
    view.setdefault("Camera", {
        "Name": "_Background Preview",
        "EyeX": -17.0,
        "EyeY": 24.0,
        "EyeZ": 50.0,
        "LookX": 12.0,
        "LookY": -13.0,
        "LookZ": -58.0,
        "UpX": 0.0,
        "UpY": 1.0,
        "UpZ": 0.0
    })
    view.setdefault("ConnectorPins", [])
    view.setdefault("Annotations", [])
    view.setdefault("X", 0.0)
    view.setdefault("Y", 0.0)
    view.setdefault("Zoom", 1.0)

    # Ensure other top-level defaults
    data.setdefault("IsCustomNode", False)
    data.setdefault("Description", "")
    data.setdefault("ElementResolver", {"ResolutionMap": {}})
    data.setdefault("Inputs", [])
    data.setdefault("Outputs", [])
    data.setdefault("Dependencies", [])
    data.setdefault("NodeLibraryDependencies", [])
    data.setdefault("EnableLegacyPolyCurveBehavior", None)
    data.setdefault("Thumbnail", "")
    data.setdefault("GraphDocumentationURL", None)
    data.setdefault("Author", "")
    data.setdefault("Linting", {
        "activeLinter": "None",
        "activeLinterId": "7b75fb44-43fd-4631-a878-29f4d5d8399a",
        "warningCount": 0,
        "errorCount": 0
    })
    data.setdefault("Bindings", [])
    data.setdefault("ExtensionWorkspaceData", [])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_empty_graph(name: str = "graph") -> Graph:
    """Create a new empty graph.

    Args:
        name: Name for the graph.

    Returns:
        Empty Graph object.
    """
    from .models import generate_guid

    return Graph(
        Uuid=generate_guid(),
        Name=name,
        Nodes=[],
        Connectors=[],
        NodeViews=[],
        _raw={}
    )
