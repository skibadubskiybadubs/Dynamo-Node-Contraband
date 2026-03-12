"""Tests for Tool 9: Node Editor (dynamo_node_edit.py)."""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.dynamo_node_edit import main
from tools.common.graph_io import load_graph

PYTHON_NODE_ID = "a8793584-ab35-45d3-a65d-9d218183d099"
NUMBER_NODE_ID = "f0216957-e451-4f20-9d2b-bd9f88c6b3c6"


@pytest.fixture
def runner():
    return CliRunner()


class TestAddInput:
    def test_add_input_to_python_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--add-input"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["input_count"] == 2
        assert data["actions"][0]["action"] == "add_input"
        assert data["actions"][0]["port_name"] == "IN[1]"

        graph = load_graph(graph_copy)
        node = graph.get_node(PYTHON_NODE_ID)
        assert len(node.Inputs) == 2

    def test_add_input_non_python_fails(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, NUMBER_NODE_ID, "--add-input"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "variable input" in data["error"].lower()


class TestRemoveInput:
    def test_remove_input(self, runner, graph_copy):
        # First add a second input
        runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--add-input"])
        # Then remove the first one
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--remove-input", "0"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["input_count"] == 1

    def test_remove_input_removes_connector(self, runner, graph_copy):
        """Removing an input with a connector should also remove the connector."""
        # IN[0] on the Python node is connected to Number output
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--remove-input", "0"])
        assert result.exit_code == 0

        graph = load_graph(graph_copy)
        assert len(graph.Connectors) == 0

    def test_remove_input_reindexes(self, runner, graph_copy):
        """After removing input 0, remaining inputs should be re-indexed."""
        # Add two more inputs (total: IN[0], IN[1], IN[2])
        runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--add-input"])
        runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--add-input"])
        # Remove IN[0]
        runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--remove-input", "0"])

        graph = load_graph(graph_copy)
        node = graph.get_node(PYTHON_NODE_ID)
        assert len(node.Inputs) == 2
        assert node.Inputs[0].Name == "IN[0]"
        assert node.Inputs[1].Name == "IN[1]"

    def test_remove_input_out_of_range(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--remove-input", "5"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "out of range" in data["error"].lower()


class TestSetValue:
    def test_set_number_value(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, NUMBER_NODE_ID, "--set-value", "99.5"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["actions"][0]["value"] == 99.5

        graph = load_graph(graph_copy)
        node = graph.get_node(NUMBER_NODE_ID)
        assert node._extra["InputValue"] == 99.5

    def test_set_string_value(self, runner, graph_copy):
        """For non-number nodes, set value as string."""
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--set-value", "hello"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["actions"][0]["value"] == "hello"


class TestRename:
    def test_rename_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--rename", "MyScript"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["actions"][0]["old_name"] == "Doubler"
        assert data["actions"][0]["new_name"] == "MyScript"

        graph = load_graph(graph_copy)
        view = graph.get_node_view(PYTHON_NODE_ID)
        assert view.Name == "MyScript"

    def test_rename_by_name(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--name", "Doubler", "--rename", "Tripler"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True

        graph = load_graph(graph_copy)
        view = graph.get_node_view(PYTHON_NODE_ID)
        assert view.Name == "Tripler"
