"""Tests for Tool 6: Output Reader (dynamo_output_read.py)."""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.dynamo_output_read import main, parse_execution_xml, get_node_outputs


@pytest.fixture
def runner():
    return CliRunner()


class TestParseXml:
    def test_parse_all_nodes(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        assert data["evaluation_count"] == 1
        eval0 = data["evaluations"][0]
        assert len(eval0["nodes"]) == 3

    def test_number_output(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = data["evaluations"][0]["nodes"][0]
        assert node["guid"] == "e2a6a828-19cb-40ab-b36c-cde2ebab1ed3"
        assert len(node["outputs"]) == 1
        out = node["outputs"][0]
        assert out["value"] == 42
        assert out["type"] == "number"

    def test_string_output(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = data["evaluations"][0]["nodes"][1]
        out0 = node["outputs"][0]
        assert out0["value"] == "Hello World"
        assert out0["type"] == "string"

    def test_list_output(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = data["evaluations"][0]["nodes"][1]
        out1 = node["outputs"][1]
        assert out1["type"] == "list"
        assert out1["raw_value"] == "[1, 2, 3]"

    def test_boolean_output(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = data["evaluations"][0]["nodes"][2]
        out0 = node["outputs"][0]
        assert out0["value"] is True
        assert out0["type"] == "boolean"

    def test_null_output(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = data["evaluations"][0]["nodes"][2]
        out1 = node["outputs"][1]
        assert out1["value"] is None
        assert out1["type"] == "null"

    def test_float_output(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = data["evaluations"][0]["nodes"][2]
        out2 = node["outputs"][2]
        assert out2["value"] == pytest.approx(3.14)
        assert out2["type"] == "number"

    def test_outputs_sorted_by_index(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        for node in data["evaluations"][0]["nodes"]:
            indices = [o["index"] for o in node["outputs"]]
            assert indices == sorted(indices)


class TestGetNodeOutputs:
    def test_find_node(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = get_node_outputs(data, "e2a6a828-19cb-40ab-b36c-cde2ebab1ed3")
        assert node is not None
        assert node["guid"] == "e2a6a828-19cb-40ab-b36c-cde2ebab1ed3"

    def test_node_not_found(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = get_node_outputs(data, "nonexistent-guid")
        assert node is None

    def test_invalid_evaluation_index(self, sample_xml):
        data = parse_execution_xml(sample_xml)
        node = get_node_outputs(data, "e2a6a828-19cb-40ab-b36c-cde2ebab1ed3", evaluation_index=99)
        assert node is None


class TestCli:
    def test_show_all_outputs(self, runner, sample_xml):
        result = runner.invoke(main, [sample_xml])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["evaluation_count"] == 1

    def test_filter_by_node(self, runner, sample_xml):
        result = runner.invoke(main, [sample_xml, "--node", "e2a6a828-19cb-40ab-b36c-cde2ebab1ed3"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["node"]["guid"] == "e2a6a828-19cb-40ab-b36c-cde2ebab1ed3"

    def test_node_not_found_cli(self, runner, sample_xml):
        result = runner.invoke(main, [sample_xml, "--node", "nonexistent"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False

    def test_invalid_xml(self, runner, tmp_path):
        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("not xml at all <<<", encoding="utf-8")
        result = runner.invoke(main, [str(bad_xml)])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert "xml" in data["error"].lower()


class TestMultipleEvaluations:
    def test_two_evaluations(self, tmp_path):
        xml = """<?xml version="1.0" encoding="utf-8"?>
<evaluations>
  <evaluation0>
    <Node guid="aaa"><output0 value="10" /></Node>
  </evaluation0>
  <evaluation1>
    <Node guid="aaa"><output0 value="20" /></Node>
  </evaluation1>
</evaluations>"""
        path = tmp_path / "multi.xml"
        path.write_text(xml, encoding="utf-8")

        data = parse_execution_xml(str(path))
        assert data["evaluation_count"] == 2
        assert data["evaluations"][0]["evaluation_index"] == 0
        assert data["evaluations"][1]["evaluation_index"] == 1

        node0 = get_node_outputs(data, "aaa", evaluation_index=0)
        assert node0["outputs"][0]["value"] == 10

        node1 = get_node_outputs(data, "aaa", evaluation_index=1)
        assert node1["outputs"][0]["value"] == 20
