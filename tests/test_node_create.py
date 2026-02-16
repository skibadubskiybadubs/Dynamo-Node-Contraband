"""Tests for Tool 2: Node Creator (dynamo_node_create.py)."""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.dynamo_node_create import main
from tools.common.graph_io import load_graph


@pytest.fixture
def runner():
    return CliRunner()


class TestPythonNode:
    def test_create_python_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "python", "--name", "TestScript"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node_type"] == "PythonScriptNode"
        assert len(data["input_ports"]) == 1
        assert len(data["output_ports"]) == 1
        assert data["input_ports"][0]["name"] == "IN[0]"
        assert data["output_ports"][0]["name"] == "OUT"

    def test_python_node_with_multiple_inputs(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "python", "--name", "Multi", "--inputs", "3"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["input_ports"]) == 3
        names = [p["name"] for p in data["input_ports"]]
        assert names == ["IN[0]", "IN[1]", "IN[2]"]

    def test_python_node_with_position(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "python", "--name", "Pos", "--position", "100,200"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["position"]["x"] == 100.0
        assert data["position"]["y"] == 200.0

    def test_python_node_persisted(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "python", "--name", "Persisted"])
        data = json.loads(result.output)
        node_id = data["node_id"]

        graph = load_graph(graph_copy)
        assert graph.get_node(node_id) is not None
        assert len(graph.Nodes) == 3  # 2 original + 1 new
        node = graph.get_node(node_id)
        assert node.is_python_node
        assert node.code is not None


class TestNumberNode:
    def test_create_number_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "number", "--value", "99.5"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node_type"] == "NumberInputNode"
        assert len(data["input_ports"]) == 0
        assert len(data["output_ports"]) == 1

    def test_number_node_value_persisted(self, runner, graph_copy):
        runner.invoke(main, [graph_copy, "number", "--value", "77"])
        graph = load_graph(graph_copy)
        num_nodes = [n for n in graph.Nodes if n.NodeType == "NumberInputNode"]
        values = [n._extra.get("InputValue") for n in num_nodes]
        assert 77.0 in values

    def test_invalid_number_value(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "number", "--value", "not_a_number"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False


class TestStringNode:
    def test_create_string_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "string", "--value", "hello world"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node_type"] == "StringInputNode"

    def test_string_node_value_persisted(self, runner, graph_copy):
        runner.invoke(main, [graph_copy, "string", "--value", "test_value"])
        graph = load_graph(graph_copy)
        str_nodes = [n for n in graph.Nodes if n.NodeType == "StringInputNode"]
        assert len(str_nodes) == 1
        assert str_nodes[0]._extra["InputValue"] == "test_value"


class TestRelativePositioning:
    def test_right_of_by_name(self, runner, graph_copy):
        """Number node is at (50, 100). --right-of should place at (350, 100)."""
        result = runner.invoke(main, [graph_copy, "python", "--name", "RightNode", "--right-of", "Number"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["position"]["x"] == 350.0
        assert data["position"]["y"] == 100.0

    def test_below_by_guid(self, runner, graph_copy):
        """Number node at (50, 100). --below should place at (50, 250)."""
        NUMBER_NODE_ID = "f0216957-e451-4f20-9d2b-bd9f88c6b3c6"
        result = runner.invoke(main, [graph_copy, "python", "--name", "BelowNode", "--below", NUMBER_NODE_ID])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["position"]["x"] == 50.0
        assert data["position"]["y"] == 250.0

    def test_right_of_and_below(self, runner, graph_copy):
        """--right-of Number (50,100) + --below Doubler (250,100) → (350, 250)."""
        result = runner.invoke(main, [
            graph_copy, "python", "--name", "Combo",
            "--right-of", "Number", "--below", "Doubler"
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["position"]["x"] == 350.0
        assert data["position"]["y"] == 250.0


class TestNodeView:
    def test_node_view_created(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "python", "--name", "ViewTest", "--position", "300,400"])
        data = json.loads(result.output)
        node_id = data["node_id"]

        graph = load_graph(graph_copy)
        view = graph.get_node_view(node_id)
        assert view is not None
        assert view.X == 300.0
        assert view.Y == 400.0
        assert view.Name == "ViewTest"
