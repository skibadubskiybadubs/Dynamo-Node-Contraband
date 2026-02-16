"""Tests for Tool 4: Code Injector (dynamo_code_inject.py)."""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.dynamo_code_inject import main
from tools.common.graph_io import load_graph

PYTHON_NODE_ID = "a8793584-ab35-45d3-a65d-9d218183d099"
NUMBER_NODE_ID = "f0216957-e451-4f20-9d2b-bd9f88c6b3c6"


@pytest.fixture
def runner():
    return CliRunner()


class TestGetCode:
    def test_get_existing_code(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--get"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node_id"] == PYTHON_NODE_ID
        assert "OUT = IN[0] * 2" in data["code"]
        assert data["code_length"] > 0

    def test_get_code_non_python_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, NUMBER_NODE_ID, "--get"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "not a Python" in data["error"]

    def test_get_code_node_not_found(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, "00000000-0000-0000-0000-000000000000", "--get"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "not found" in data["error"].lower()


class TestInjectInlineCode:
    def test_inject_code(self, runner, graph_copy):
        new_code = "OUT = IN[0] + 100"
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--code", new_code])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["code_length"] == len(new_code)
        assert data["syntax_valid"] is True

        # Verify persisted
        graph = load_graph(graph_copy)
        node = graph.get_node(PYTHON_NODE_ID)
        assert node.code == new_code

    def test_inject_multiline_code(self, runner, graph_copy):
        new_code = "x = IN[0]\ny = x * 2\nOUT = y"
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--code", new_code])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["syntax_valid"] is True

    def test_inject_invalid_syntax(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--code", "def broken("])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "syntax error" in data["error"].lower()

    def test_inject_invalid_syntax_skip_validation(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--code", "def broken(", "--no-validate"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True

    def test_inject_to_non_python_node(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, NUMBER_NODE_ID, "--code", "OUT = 1"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False


class TestInjectFromFile:
    def test_inject_from_file(self, runner, graph_copy, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("result = IN[0] ** 2\nOUT = result", encoding="utf-8")

        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID, "--file", str(script)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["syntax_valid"] is True

        graph = load_graph(graph_copy)
        assert "IN[0] ** 2" in graph.get_node(PYTHON_NODE_ID).code


class TestNoOperation:
    def test_no_code_or_file_or_get(self, runner, graph_copy):
        result = runner.invoke(main, [graph_copy, PYTHON_NODE_ID])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
