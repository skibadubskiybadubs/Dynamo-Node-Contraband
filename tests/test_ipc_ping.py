#!/usr/bin/env python
"""Quick connectivity test for DynamoCliAddIn IPC bridge.

Prerequisites:
    - Revit 2025 running with DynamoCliAddIn installed
    - pip install pywin32

Usage:
    python tests/test_ipc_ping.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.common.ipc_client import (
    IpcConnectionError,
    IpcError,
    IpcTimeoutError,
    get_status,
    ping,
)


def main():
    print("=== DynamoCliAddIn IPC Connectivity Test ===\n")

    # Test 1: Ping
    print("[1/2] Sending ping...")
    try:
        result = ping(timeout=10)
        print(f"  OK: {result.get('message')}")
        print(f"  Revit version: {result.get('revit_version')}")
        print(f"  Document: {result.get('document_name', '(none)')}")
        print(f"  Dynamo loaded: {result.get('dynamo_loaded')}")
    except IpcConnectionError as e:
        print(f"  FAIL: {e}")
        print("\n  Make sure Revit 2025 is running with DynamoCliAddIn installed.")
        sys.exit(1)
    except IpcTimeoutError as e:
        print(f"  TIMEOUT: {e}")
        sys.exit(1)
    except IpcError as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    # Test 2: Status
    print("\n[2/2] Getting status...")
    try:
        result = get_status(timeout=10)
        print(f"  Revit version: {result.get('revit_version')}")
        print(f"  Document open: {result.get('document_open')}")
        print(f"  Document name: {result.get('document_name', '(none)')}")
        print(f"  Document path: {result.get('document_path', '(none)')}")
        print(f"  Dynamo loaded: {result.get('dynamo_loaded')}")
    except IpcError as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print("\n=== All tests passed ===")


if __name__ == "__main__":
    main()
