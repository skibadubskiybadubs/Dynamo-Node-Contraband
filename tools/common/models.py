"""Data models for Dynamo graph elements."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid


def generate_guid() -> str:
    """Generate a new GUID string."""
    return str(uuid.uuid4())


@dataclass
class Port:
    """Represents an input or output port on a node."""
    Id: str
    Name: str
    Description: str = ""
    UsingDefaultValue: bool = False
    Level: int = 2
    UseLevels: bool = False
    KeepListStructure: bool = False

    @classmethod
    def create(cls, name: str, description: str = "") -> "Port":
        """Create a new port with a generated GUID."""
        return cls(
            Id=generate_guid().replace("-", ""),
            Name=name,
            Description=description
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "Id": self.Id,
            "Name": self.Name,
            "Description": self.Description,
            "UsingDefaultValue": self.UsingDefaultValue,
            "Level": self.Level,
            "UseLevels": self.UseLevels,
            "KeepListStructure": self.KeepListStructure
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Port":
        """Create from dictionary."""
        return cls(
            Id=data["Id"],
            Name=data.get("Name", ""),
            Description=data.get("Description", ""),
            UsingDefaultValue=data.get("UsingDefaultValue", False),
            Level=data.get("Level", 2),
            UseLevels=data.get("UseLevels", False),
            KeepListStructure=data.get("KeepListStructure", False)
        )


@dataclass
class Node:
    """Represents a node in a Dynamo graph."""
    Id: str
    NodeType: str
    ConcreteType: str
    Inputs: List[Port] = field(default_factory=list)
    Outputs: List[Port] = field(default_factory=list)
    Replication: str = "Disabled"
    Description: str = ""

    # Additional properties stored in _extra for round-trip preservation
    _extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_python_node(self) -> bool:
        """Check if this is a Python Script node."""
        return self.NodeType == "PythonScriptNode"

    @property
    def code(self) -> Optional[str]:
        """Get Python code if this is a Python node."""
        if self.is_python_node:
            return self._extra.get("Code", "")
        return None

    @code.setter
    def code(self, value: str):
        """Set Python code (only for Python nodes)."""
        if not self.is_python_node:
            raise ValueError("Cannot set code on non-Python node")
        self._extra["Code"] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "Id": self.Id,
            "NodeType": self.NodeType,
            "ConcreteType": self.ConcreteType,
            "Inputs": [p.to_dict() for p in self.Inputs],
            "Outputs": [p.to_dict() for p in self.Outputs],
            "Replication": self.Replication,
            "Description": self.Description,
        }
        # Merge extra properties (Code, Engine, InputValue, etc.)
        result.update(self._extra)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        """Create from dictionary."""
        # Known fields
        known_fields = {"Id", "NodeType", "ConcreteType", "Inputs", "Outputs",
                        "Replication", "Description"}

        # Extract extra fields
        extra = {k: v for k, v in data.items() if k not in known_fields}

        return cls(
            Id=data["Id"],
            NodeType=data.get("NodeType", ""),
            ConcreteType=data.get("ConcreteType", ""),
            Inputs=[Port.from_dict(p) for p in data.get("Inputs", [])],
            Outputs=[Port.from_dict(p) for p in data.get("Outputs", [])],
            Replication=data.get("Replication", "Disabled"),
            Description=data.get("Description", ""),
            _extra=extra
        )


@dataclass
class Connector:
    """Represents a connection between two ports."""
    Id: str
    Start: str  # Output port GUID
    End: str    # Input port GUID
    IsHidden: str = "False"

    @classmethod
    def create(cls, start_port: str, end_port: str) -> "Connector":
        """Create a new connector with a generated GUID."""
        return cls(
            Id=generate_guid(),
            Start=start_port,
            End=end_port
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "Id": self.Id,
            "Start": self.Start,
            "End": self.End,
            "IsHidden": self.IsHidden
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Connector":
        """Create from dictionary."""
        return cls(
            Id=data["Id"],
            Start=data["Start"],
            End=data["End"],
            IsHidden=data.get("IsHidden", "False")
        )


@dataclass
class NodeView:
    """Represents the visual properties of a node on the canvas."""
    Id: str  # Must match Node.Id
    Name: str = ""
    IsSetAsInput: bool = False
    IsSetAsOutput: bool = False
    Excluded: bool = False
    ShowGeometry: bool = True
    X: float = 0.0
    Y: float = 0.0

    @classmethod
    def create(cls, node_id: str, name: str = "", x: float = 0.0, y: float = 0.0) -> "NodeView":
        """Create a new NodeView for a node."""
        return cls(Id=node_id, Name=name, X=x, Y=y)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "Id": self.Id,
            "Name": self.Name,
            "IsSetAsInput": self.IsSetAsInput,
            "IsSetAsOutput": self.IsSetAsOutput,
            "Excluded": self.Excluded,
            "ShowGeometry": self.ShowGeometry,
            "X": self.X,
            "Y": self.Y
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeView":
        """Create from dictionary."""
        return cls(
            Id=data.get("Id", ""),
            Name=data.get("Name", ""),
            IsSetAsInput=data.get("IsSetAsInput", False),
            IsSetAsOutput=data.get("IsSetAsOutput", False),
            Excluded=data.get("Excluded", False),
            ShowGeometry=data.get("ShowGeometry", True),
            X=data.get("X", 0.0),
            Y=data.get("Y", 0.0)
        )


@dataclass
class Graph:
    """Represents a complete Dynamo graph."""
    Uuid: str
    Name: str
    Nodes: List[Node] = field(default_factory=list)
    Connectors: List[Connector] = field(default_factory=list)
    NodeViews: List[NodeView] = field(default_factory=list)

    # Store the complete raw data for round-trip preservation
    _raw: Dict[str, Any] = field(default_factory=dict)

    def get_node(self, node_id: str) -> Optional[Node]:
        """Find a node by ID."""
        for node in self.Nodes:
            if node.Id == node_id:
                return node
        return None

    def get_node_view(self, node_id: str) -> Optional[NodeView]:
        """Find a node view by node ID."""
        for nv in self.NodeViews:
            if nv.Id == node_id:
                return nv
        return None

    def find_port_owner(self, port_id: str) -> Optional[Node]:
        """Find the node that owns a given port."""
        for node in self.Nodes:
            for port in node.Inputs + node.Outputs:
                if port.Id == port_id:
                    return node
        return None

    def get_connections_for_node(self, node_id: str) -> List[Connector]:
        """Get all connections involving a node's ports."""
        node = self.get_node(node_id)
        if not node:
            return []

        port_ids = {p.Id for p in node.Inputs + node.Outputs}
        return [c for c in self.Connectors if c.Start in port_ids or c.End in port_ids]

    def add_node(self, node: Node, view: Optional[NodeView] = None):
        """Add a node to the graph."""
        self.Nodes.append(node)
        if view:
            self.NodeViews.append(view)
        elif not self.get_node_view(node.Id):
            # Create default view
            self.NodeViews.append(NodeView.create(node.Id))

    def add_connector(self, connector: Connector):
        """Add a connector to the graph."""
        self.Connectors.append(connector)

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its view from the graph."""
        node = self.get_node(node_id)
        if not node:
            return False

        self.Nodes.remove(node)

        view = self.get_node_view(node_id)
        if view:
            self.NodeViews.remove(view)

        # Remove associated connectors
        port_ids = {p.Id for p in node.Inputs + node.Outputs}
        self.Connectors = [c for c in self.Connectors
                          if c.Start not in port_ids and c.End not in port_ids]

        return True

    def remove_connector(self, connector_id: str) -> bool:
        """Remove a connector from the graph."""
        for i, c in enumerate(self.Connectors):
            if c.Id == connector_id:
                self.Connectors.pop(i)
                return True
        return False
