"""Tests for Tool 5: Graph Executor (dynamo_execute.py).

Note: These tests mock subprocess.run since DynamoCLI.exe may not be
available in all environments. The CLI integration is tested separately.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.dynamo_execute import execute_graph


class TestExecuteGraph:
    @patch("tools.dynamo_execute.get_dynamo_cli_path")
    def test_cli_not_found(self, mock_cli_path):
        mock_cli_path.return_value = "C:\\nonexistent\\DynamoCLI.exe"
        result = execute_graph("test.dyn")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch("tools.dynamo_execute.subprocess.run")
    @patch("tools.dynamo_execute.get_dynamo_cli_path")
    @patch("tools.dynamo_execute.os.path.exists", return_value=True)
    def test_successful_execution(self, mock_exists, mock_cli_path, mock_run):
        mock_cli_path.return_value = "C:\\DynamoCLI.exe"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Graph executed successfully",
            stderr=""
        )
        result = execute_graph("test.dyn", timeout=30)
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "execution_time_ms" in result

    @patch("tools.dynamo_execute.subprocess.run")
    @patch("tools.dynamo_execute.get_dynamo_cli_path")
    @patch("tools.dynamo_execute.os.path.exists", return_value=True)
    def test_execution_with_output(self, mock_exists, mock_cli_path, mock_run):
        mock_cli_path.return_value = "C:\\DynamoCLI.exe"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = execute_graph("test.dyn", output_xml="output.xml")
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-v" in cmd

    @patch("tools.dynamo_execute.subprocess.run")
    @patch("tools.dynamo_execute.get_dynamo_cli_path")
    @patch("tools.dynamo_execute.os.path.exists", return_value=True)
    def test_execution_failure(self, mock_exists, mock_cli_path, mock_run):
        mock_cli_path.return_value = "C:\\DynamoCLI.exe"
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: graph failed"
        )
        result = execute_graph("test.dyn")
        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "graph failed" in result["stderr"]

    @patch("tools.dynamo_execute.subprocess.run")
    @patch("tools.dynamo_execute.get_dynamo_cli_path")
    @patch("tools.dynamo_execute.os.path.exists", return_value=True)
    def test_execution_timeout(self, mock_exists, mock_cli_path, mock_run):
        import subprocess
        mock_cli_path.return_value = "C:\\DynamoCLI.exe"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)

        result = execute_graph("test.dyn", timeout=5)
        assert result["success"] is False
        assert "timed out" in result["error"].lower()
        assert result["exit_code"] == -1


class TestOutputFormat:
    @patch("tools.dynamo_execute.subprocess.run")
    @patch("tools.dynamo_execute.get_dynamo_cli_path")
    @patch("tools.dynamo_execute.os.path.exists", return_value=True)
    def test_result_has_all_fields(self, mock_exists, mock_cli_path, mock_run):
        mock_cli_path.return_value = "C:\\DynamoCLI.exe"
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        result = execute_graph("test.dyn")
        required_keys = {"success", "exit_code", "execution_time_ms", "output_xml", "stdout", "stderr"}
        assert required_keys.issubset(set(result.keys()))
