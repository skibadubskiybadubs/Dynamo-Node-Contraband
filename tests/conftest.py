"""Shared test fixtures for Dynamo CLI tool tests."""

import json
import shutil
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
GRAPH_PATH = TESTS_DIR / "graph.dyn"


@pytest.fixture
def graph_copy(tmp_path):
    """Create a temporary copy of graph.dyn for tests that modify it."""
    dest = tmp_path / "graph.dyn"
    shutil.copy(GRAPH_PATH, dest)
    return str(dest)


@pytest.fixture
def empty_graph(tmp_path):
    """Create an empty .dyn graph in a temp directory."""
    import sys
    sys.path.insert(0, str(TESTS_DIR.parent))
    from tools.common.graph_io import create_empty_graph, save_graph

    graph = create_empty_graph("test_graph")
    path = tmp_path / "empty.dyn"
    save_graph(graph, str(path))
    return str(path)


@pytest.fixture
def sample_xml(tmp_path):
    """Create a sample DynamoCLI XML output file."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<evaluations>
  <evaluation0>
    <Node guid="e2a6a828-19cb-40ab-b36c-cde2ebab1ed3">
      <output0 value="42" />
    </Node>
    <Node guid="67139026-e3a5-445c-8ba5-8a28be5d1be0">
      <output0 value="Hello World" />
      <output1 value="[1, 2, 3]" />
    </Node>
    <Node guid="aaa11111-0000-0000-0000-000000000000">
      <output0 value="true" />
      <output1 value="null" />
      <output2 value="3.14" />
    </Node>
  </evaluation0>
</evaluations>"""
    path = tmp_path / "output.xml"
    path.write_text(xml_content, encoding="utf-8")
    return str(path)
