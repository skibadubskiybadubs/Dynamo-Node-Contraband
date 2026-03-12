"""Tests for Tool 3: Node Connector (dynamo_node_connect.py)."""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.dynamo_node_connect import main
from tools.common.graph_io import load_graph

# Known port GUIDs from tests/graph.dyn
NUMBER_OUT_PORT = "6bea04e8331e47c8b77c276f046ea459"
PYTHON_IN_PORT = "d9c091db586140fd80bffe65d05a4037"
PYTHON_OUT_PORT = "64aeda7375fa4e35b7991913df6cd075"
EXISTING_CONNECTOR_ID = "a2fa595a-5056-4be5-a470-71c3803dcaff"
NUMBER_NODE_ID = "f0216957-e451-4f20-9d2b-bd9f88c6b3c6"
PYTHON_NODE_ID = "a8793584-ab35-45d3-a65d-9d218183d099"


@pytest.fixture
def runner():
    return CliRunner()


class TestListPorts:
    def test_list_ports_number_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--list-ports", NUMBER_NODE_ID])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node_type"] == "NumberInputNode"
        assert len(data["input_ports"]) == 0
        assert len(data["output_ports"]) == 1
        assert data["output_ports"][0]["id"] == NUMBER_OUT_PORT

    def test_list_ports_python_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--list-ports", PYTHON_NODE_ID])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["input_ports"]) == 1
        assert len(data["output_ports"]) == 1

    def test_list_ports_not_found(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--list-ports", "00000000-0000-0000-0000-000000000000"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False


class TestConnect:
    def test_duplicate_connection_rejected(self, runner, graph_copy):
        """The existing connector connects NUMBER_OUT -> PYTHON_IN already."""
        result = runner.invoke(main, [graph_copy, "--from", NUMBER_OUT_PORT, "--to", PYTHON_IN_PORT])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "already exists" in data["error"].lower()

    def test_connect_new_nodes(self, runner, graph_copy):
        """Add a new node, then connect its output to the Python node's input after removing existing connector."""
        # First disconnect existing
        runner.invoke(main, [graph_copy, "--disconnect", EXISTING_CONNECTOR_ID])

        # Now reconnect with new connector
        result = runner.invoke(main, [graph_copy, "--from", NUMBER_OUT_PORT, "--to", PYTHON_IN_PORT])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["action"] == "connected"
        assert data["from_port"] == NUMBER_OUT_PORT
        assert data["to_port"] == PYTHON_IN_PORT

        # Verify persisted
        graph = load_graph(graph_copy)
        assert len(graph.Connectors) == 1

    def test_connect_wrong_port_direction(self, runner, graph_copy):
        """from_port must be an output, to_port must be an input."""
        result = runner.invoke(main, [graph_copy, "--from", PYTHON_IN_PORT, "--to", NUMBER_OUT_PORT])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "not an output" in data["error"].lower()

    def test_connect_invalid_port(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--from", "bogus-port-id", "--to", PYTHON_IN_PORT])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False

    def test_no_operation_specified(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False


class TestConnectByName:
    def test_connect_by_name(self, runner, graph_copy):
        """Remove existing connection, then reconnect using node names."""
        runner.invoke(main, [graph_copy, "--disconnect", EXISTING_CONNECTOR_ID])
        result = runner.invoke(main, [graph_copy, "--from-node", "Number", "--to-node", "Doubler"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["action"] == "connected"

    def test_mixed_mode(self, runner, graph_copy):
        """Use --from-node with --to port GUID."""
        runner.invoke(main, [graph_copy, "--disconnect", EXISTING_CONNECTOR_ID])
        result = runner.invoke(main, [graph_copy, "--from-node", "Number", "--to", PYTHON_IN_PORT])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True

    def test_name_not_found(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--from-node", "NoSuchNode", "--to-node", "Doubler"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_no_available_input(self, runner, graph_copy):
        """Doubler's only input is already connected, so --to-node should fail."""
        result = runner.invoke(main, [graph_copy, "--from-node", "Number", "--to-node", "Doubler"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "no available input" in data["error"].lower()


class TestDisconnect:
    def test_disconnect(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--disconnect", EXISTING_CONNECTOR_ID])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["action"] == "disconnected"

        graph = load_graph(graph_copy)
        assert len(graph.Connectors) == 0

    def test_disconnect_not_found(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "--disconnect", "00000000-0000-0000-0000-000000000000"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
