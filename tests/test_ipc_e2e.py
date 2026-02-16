#!/usr/bin/env python
"""End-to-end integration tests for the DynamoCliAddIn IPC bridge.

Prerequisites:
    - Revit 2025 running with DynamoCliAddIn installed
    - A Dynamo graph open in Automatic run mode
    - pip install pywin32

Usage:
    python tests/test_ipc_e2e.py                          # Run all tests
    python tests/test_ipc_e2e.py --graph tests/revit_test.dyn  # Specify graph path
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.ipc_client import (
    IpcConnectionError,
    IpcError,
    IpcTimeoutError,
    execute_graph,
    get_status,
    is_available,
    ping,
    send_request,
)

PASS = 0
FAIL = 0
SKIP = 0


def log_pass(name: str, detail: str = ""):
    global PASS
    PASS += 1
    suffix = f" - {detail}" if detail else ""
    print(f"  PASS  {name}{suffix}")


def log_fail(name: str, detail: str = ""):
    global FAIL
    FAIL += 1
    suffix = f" - {detail}" if detail else ""
    print(f"  FAIL  {name}{suffix}")


def log_skip(name: str, reason: str = ""):
    global SKIP
    SKIP += 1
    suffix = f" - {reason}" if reason else ""
    print(f"  SKIP  {name}{suffix}")


# ── Test functions ────────────────────────────────────────────────────


def test_is_available():
    """Verify is_available() returns True when Revit is running."""
    name = "is_available()"
    try:
        result = is_available(timeout=5)
        if result:
            log_pass(name)
        else:
            log_fail(name, "returned False")
    except Exception as e:
        log_fail(name, str(e))


def test_ping():
    """Verify ping returns expected fields."""
    name = "ping"
    try:
        data = ping(timeout=10)
        assert data.get("message") == "pong", f"expected pong, got {data.get('message')}"
        assert "revit_version" in data, "missing revit_version"
        assert "dynamo_loaded" in data, "missing dynamo_loaded"
        log_pass(name, f"revit={data['revit_version']} dynamo={data['dynamo_loaded']}")
    except AssertionError as e:
        log_fail(name, str(e))
    except Exception as e:
        log_fail(name, str(e))


def test_status():
    """Verify status returns expected fields."""
    name = "status"
    try:
        data = get_status(timeout=10)
        assert "revit_version" in data, "missing revit_version"
        assert "document_open" in data, "missing document_open"
        assert "dynamo_loaded" in data, "missing dynamo_loaded"
        log_pass(name, f"doc={data.get('document_name', '(none)')}")
    except AssertionError as e:
        log_fail(name, str(e))
    except Exception as e:
        log_fail(name, str(e))


def test_unknown_command():
    """Verify unknown commands return an error."""
    name = "unknown_command"
    try:
        resp = send_request("nonexistent_cmd", timeout=10)
        if not resp.get("success"):
            log_pass(name, f"error={resp.get('error', '')[:60]}")
        else:
            log_fail(name, "expected failure but got success")
    except Exception as e:
        log_fail(name, str(e))


def test_execute_missing_graph():
    """Verify execute with a non-existent graph returns an error."""
    name = "execute_missing_graph"
    try:
        resp = execute_graph("C:\\nonexistent\\fake_graph.dyn", timeout=15)
        if not resp.get("success"):
            log_pass(name, "correctly returned error for missing graph")
        else:
            log_fail(name, "expected failure but got success")
    except Exception as e:
        log_fail(name, str(e))


def test_execute_graph(graph_path: str):
    """Execute a real graph and validate the response structure."""
    name = "execute_graph"

    # Check if Dynamo is loaded first
    try:
        data = ping(timeout=5)
        if not data.get("dynamo_loaded"):
            log_skip(name, "Dynamo not loaded - open a graph first")
            return
    except Exception:
        log_skip(name, "cannot ping Revit")
        return

    try:
        resp = execute_graph(graph_path, timeout=60)
        if not resp.get("success"):
            log_fail(name, f"error={resp.get('error', '')[:80]}")
            return

        data = resp.get("data", {})
        nodes = data.get("nodes", [])
        count = data.get("node_count", 0)

        if count == 0:
            log_fail(name, "no nodes returned")
            return

        # Verify node structure
        sample = nodes[0]
        required_keys = {"id", "name", "type", "state", "value"}
        missing = required_keys - set(sample.keys())
        if missing:
            log_fail(name, f"node missing keys: {missing}")
            return

        # Check if any nodes have non-null values
        valued = [n for n in nodes if n.get("value") is not None]
        log_pass(name, f"{count} nodes, {len(valued)} with values")

    except IpcTimeoutError:
        log_fail(name, "timeout waiting for graph execution")
    except Exception as e:
        log_fail(name, str(e))


def test_execute_graph_reload(graph_path: str):
    """Execute with --reload flag and verify it works."""
    name = "execute_graph_reload"

    try:
        data = ping(timeout=5)
        if not data.get("dynamo_loaded"):
            log_skip(name, "Dynamo not loaded")
            return
    except Exception:
        log_skip(name, "cannot ping Revit")
        return

    try:
        resp = execute_graph(graph_path, timeout=60, reload=True)
        if not resp.get("success"):
            log_fail(name, f"error={resp.get('error', '')[:80]}")
            return

        count = resp.get("data", {}).get("node_count", 0)
        log_pass(name, f"reload succeeded, {count} nodes")
    except Exception as e:
        log_fail(name, str(e))


def test_rapid_ping():
    """Verify multiple rapid pings work (pipe concurrency)."""
    name = "rapid_ping (3x)"
    try:
        for i in range(3):
            data = ping(timeout=10)
            assert data.get("message") == "pong"
        log_pass(name)
    except Exception as e:
        log_fail(name, str(e))


# ── Main ──────────────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DynamoCliAddIn E2E Tests")
    parser.add_argument("--graph", type=str, default=None,
                        help="Path to a .dyn graph for execute tests")
    args = parser.parse_args()

    # Resolve graph path
    graph_path = args.graph
    if graph_path is None:
        default = Path(__file__).parent / "revit_test.dyn"
        if default.exists():
            graph_path = str(default.resolve())

    print("=" * 60)
    print("  DynamoCliAddIn - End-to-End Integration Tests")
    print("=" * 60)
    print()

    # Check connectivity first
    print("[Connectivity]")
    if not is_available(timeout=5):
        print("  FAIL  Cannot reach Revit IPC bridge.")
        print("        Is Revit 2025 running with DynamoCliAddIn?")
        sys.exit(1)
    print("  OK    Revit IPC bridge reachable")
    print()

    # Run tests
    print("[Basic Commands]")
    test_is_available()
    test_ping()
    test_status()
    test_unknown_command()
    test_rapid_ping()
    print()

    print("[Graph Execution]")
    test_execute_missing_graph()
    if graph_path:
        test_execute_graph(graph_path)
        test_execute_graph_reload(graph_path)
    else:
        log_skip("execute_graph", "no --graph provided and tests/revit_test.dyn not found")
        log_skip("execute_graph_reload", "no graph path")
    print()

    # Summary
    total = PASS + FAIL + SKIP
    print("=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed, {SKIP} skipped / {total} total")
    print("=" * 60)

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()
