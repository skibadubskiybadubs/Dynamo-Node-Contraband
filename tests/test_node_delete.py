"""Tests for Tool 8: Node Deleter (dynamo_node_delete.py)."""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.dynamo_node_delete import main
from tools.common.graph_io import load_graph, save_graph

PYTHON_NODE_ID = "a8793584-ab35-45d3-a65d-9d218183d099"
NUMBER_NODE_ID = "f0216957-e451-4f20-9d2b-bd9f88c6b3c6"


@pytest.fixture
def runner():
    return CliRunner()


class TestDeleteByGuid:
    def test_delete_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, NUMBER_NODE_ID])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["deleted_node"]["id"] == NUMBER_NODE_ID
        assert data["remaining_nodes"] == 1

    def test_delete_not_found(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "00000000-0000-0000-0000-000000000000"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_delete_removes_connectors(self, runner, graph_copy):
        """Deleting a connected node should remove its connectors."""
        result = runner.invoke(main, [graph_copy, NUMBER_NODE_ID])
        data = json.loads(result.output)
        assert data["connectors_removed"] == 1

        graph = load_graph(graph_copy)
        assert len(graph.Connectors) == 0


class TestDeleteByName:
    def test_delete_by_name(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--name", "Number"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["deleted_node"]["name"] == "Number"

    def test_name_not_found(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--name", "NonexistentNode"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False

    def test_ambiguous_name(self, runner, graph_copy):
        """Two nodes with same name should error."""
        graph = load_graph(graph_copy)
        for nv in graph.NodeViews:
            if nv.Name == "Number":
                nv.Name = "Doubler"
        save_graph(graph, graph_copy)

        result = runner.invoke(main, [graph_copy, "--name", "Doubler"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "multiple" in data["error"].lower()


class TestDeletePersistence:
    def test_graph_saved(self, runner, graph_copy):
        runner.invoke(main, [graph_copy, NUMBER_NODE_ID])
        graph = load_graph(graph_copy)
        assert len(graph.Nodes) == 1
        assert graph.get_node(NUMBER_NODE_ID) is None
        assert graph.get_node_view(NUMBER_NODE_ID) is None
