"""Tests for Tool 1: Graph Reader (dynamo_graph_read.py)."""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.dynamo_graph_read import main
from tools.common.graph_io import load_graph


@pytest.fixture
def runner():
    return CliRunner()


class TestGraphSummary:
    def test_default_summary(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node_count"] == 2
        assert data["connector_count"] == 1
        assert data["name"] == "graph"
        assert "graph_id" in data
        assert len(data["nodes"]) == 2

    def test_summary_node_fields(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy])
        data = json.loads(result.output)
        node = data["nodes"][0]
        assert "id" in node
        assert "type" in node
        assert "inputs" in node
        assert "outputs" in node


class TestNodeListing:
    def test_list_nodes(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--nodes"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node_count"] == 2
        nodes = data["nodes"]
        types = {n["type"] for n in nodes}
        assert "NumberInputNode" in types
        assert "PythonScriptNode" in types

    def test_node_has_ports(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--nodes"])
        data = json.loads(result.output)
        python_node = [n for n in data["nodes"] if n["type"] == "PythonScriptNode"][0]
        assert python_node["input_count"] == 1
        assert python_node["output_count"] == 1
        assert len(python_node["input_ports"]) == 1
        assert len(python_node["output_ports"]) == 1

    def test_python_node_has_code_length(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--nodes"])
        data = json.loads(result.output)
        python_node = [n for n in data["nodes"] if n["type"] == "PythonScriptNode"][0]
        assert "code_length" in python_node
        assert python_node["code_length"] > 0

    def test_number_node_has_value(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--nodes"])
        data = json.loads(result.output)
        num_node = [n for n in data["nodes"] if n["type"] == "NumberInputNode"][0]
        assert "value" in num_node
        assert num_node["value"] == 42.0


class TestNodeDetail:
    def test_node_by_guid(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--node", "a8793584-ab35-45d3-a65d-9d218183d099"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        node = data["node"]
        assert node["type"] == "PythonScriptNode"
        assert "code" in node
        assert "OUT = IN[0] * 2" in node["code"]
        assert "position" in node
        assert "connections" in node

    def test_node_not_found(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--node", "00000000-0000-0000-0000-000000000000"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "not found" in data["error"].lower()


class TestConnectors:
    def test_list_connectors(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--connectors"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["connector_count"] == 1
        conn = data["connectors"][0]
        assert "from_port" in conn
        assert "to_port" in conn
        assert "from_node" in conn
        assert "to_node" in conn


class TestNodeByName:
    def test_find_by_name(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--node-name", "Doubler"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node"]["type"] == "PythonScriptNode"
        assert "code" in data["node"]

    def test_name_not_found(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--node-name", "NonexistentNode"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_name_ambiguous(self, runner, graph_copy):
        """Create ambiguity by renaming a node, then query by name."""
        from tools.common.graph_io import load_graph as _load, save_graph
        g = _load(graph_copy)
        for nv in g.NodeViews:
            if nv.Name == "Number":
                nv.Name = "Doubler"
        save_graph(g, graph_copy)

        result = runner.invoke(main, [graph_copy, "--node-name", "Doubler"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "multiple" in data["error"].lower()


class TestNameResolution:
    def test_exact_match(self, graph_copy):
        graph = load_graph(graph_copy)
        node = graph.get_node_by_name("Number")
        assert node is not None
        assert node.NodeType == "NumberInputNode"

    def test_case_insensitive(self, graph_copy):
        graph = load_graph(graph_copy)
        node = graph.get_node_by_name("number")
        assert node is not None
        assert node.NodeType == "NumberInputNode"

    def test_partial_match(self, graph_copy):
        graph = load_graph(graph_copy)
        results = graph.find_nodes_by_name("ble")
        names = [graph.get_node_view(n.Id).Name for n in results]
        assert "Doubler" in names

    def test_no_match(self, graph_copy):
        graph = load_graph(graph_copy)
        assert graph.get_node_by_name("NonexistentNode") is None
        assert graph.find_nodes_by_name("NonexistentNode") == []

    def test_ambiguous_match(self, graph_copy):
        """Two nodes with the same name should raise ValueError."""
        graph = load_graph(graph_copy)
        # Rename Number node to "Doubler" to create ambiguity
        for nv in graph.NodeViews:
            if nv.Name == "Number":
                nv.Name = "Doubler"
        with pytest.raises(ValueError, match="Multiple nodes match"):
            graph.get_node_by_name("Doubler")


class TestErrorHandling:
    def test_file_not_found(self, runner):
        result = runner.invoke(main, ["nonexistent.dyn"])
        assert result.exit_code != 0
