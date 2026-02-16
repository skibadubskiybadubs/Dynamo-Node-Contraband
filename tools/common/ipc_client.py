"""Named pipe IPC client for communicating with DynamoCliAddIn in Revit.

Uses pywin32's win32file for named pipe operations on Windows.
"""

import json
import time
import uuid
from typing import Any, Optional

import pywintypes
import win32file
import win32pipe


PIPE_NAME = r"\\.\pipe\DynamoCliAddIn"
DEFAULT_TIMEOUT = 120
CONNECT_RETRY_DELAY = 0.5
MAX_CONNECT_RETRIES = 10
BUFFER_SIZE = 65536


class IpcError(Exception):
    """Raised when IPC communication fails."""
    pass


class IpcTimeoutError(IpcError):
    """Raised when the pipe server doesn't respond in time."""
    pass


class IpcConnectionError(IpcError):
    """Raised when unable to connect to the pipe server."""
    pass


def send_request(command: str, payload: Optional[dict] = None,
                 timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Send a request to DynamoCliAddIn and return the response.

    Args:
        command: Command name (ping, status, execute).
        payload: Optional command payload.
        timeout: Timeout in seconds for the entire operation.

    Returns:
        Parsed JSON response dict.

    Raises:
        IpcConnectionError: Cannot connect to pipe (Revit not running or add-in not loaded).
        IpcTimeoutError: Connected but no response within timeout.
        IpcError: Other communication errors.
    """
    request = {
        "id": str(uuid.uuid4()),
        "command": command,
        "payload": payload or {}
    }
    request_bytes = (json.dumps(request) + "\n").encode("utf-8")

    handle = _connect_pipe(timeout)
    try:
        # Send request
        win32file.WriteFile(handle, request_bytes)

        # Read response
        response_bytes = _read_response(handle, timeout)
        response = json.loads(response_bytes.decode("utf-8").strip())
        return response

    except pywintypes.error as e:
        raise IpcError(f"Pipe communication error: {e.strerror}") from e
    finally:
        win32file.CloseHandle(handle)


def ping(timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Send a ping command and return the response data.

    Returns:
        Dict with message, revit_version, document_name, dynamo_loaded.
    """
    response = send_request("ping", timeout=timeout)
    if not response.get("success"):
        raise IpcError(f"Ping failed: {response.get('error', 'unknown error')}")
    return response.get("data", {})


def get_status(timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Get Revit status information.

    Returns:
        Dict with revit_version, document_open, document_name, document_path, dynamo_loaded.
    """
    response = send_request("status", timeout=timeout)
    if not response.get("success"):
        raise IpcError(f"Status failed: {response.get('error', 'unknown error')}")
    return response.get("data", {})


def execute_graph(graph_path: str, timeout: int = DEFAULT_TIMEOUT, reload: bool = False) -> dict:
    """Execute a Dynamo graph via Revit IPC.

    Args:
        graph_path: Absolute path to the .dyn file.
        timeout: Timeout in seconds.
        reload: Force reload of the graph from disk.

    Returns:
        Response dict with execution results.

    Raises:
        IpcError: If execution fails or returns an error.
    """
    payload = {"graph_path": graph_path, "reload": reload}
    response = send_request("execute", payload, timeout=timeout)
    return response


def is_available(timeout: int = 5) -> bool:
    """Check if the Revit IPC bridge is reachable.

    Returns True if a ping succeeds, False otherwise.
    """
    try:
        ping(timeout=timeout)
        return True
    except IpcError:
        return False


def _connect_pipe(timeout: int) -> int:
    """Connect to the named pipe with retry logic.

    Returns:
        Win32 file handle for the pipe.
    """
    deadline = time.monotonic() + timeout
    retries = 0

    while True:
        try:
            handle = win32file.CreateFile(
                PIPE_NAME,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,     # no sharing
                None,  # default security
                win32file.OPEN_EXISTING,
                0,     # default attributes
                None   # no template
            )
            return handle

        except pywintypes.error as e:
            error_code = e.winerror

            if error_code == 2:  # ERROR_FILE_NOT_FOUND - pipe doesn't exist
                if time.monotonic() >= deadline:
                    raise IpcConnectionError(
                        "Cannot connect to DynamoCliAddIn pipe. "
                        "Is Revit 2025 running with the add-in installed?"
                    ) from e
                retries += 1
                if retries > MAX_CONNECT_RETRIES:
                    raise IpcConnectionError(
                        "Cannot connect to DynamoCliAddIn pipe after "
                        f"{MAX_CONNECT_RETRIES} retries. "
                        "Is Revit 2025 running with the add-in installed?"
                    ) from e
                time.sleep(CONNECT_RETRY_DELAY)

            elif error_code == 231:  # ERROR_PIPE_BUSY
                # Wait for pipe to become available. WaitNamedPipe itself can
                # fail with ERROR_FILE_NOT_FOUND if the server is recycling
                # its pipe instance, so treat that as a transient retry.
                try:
                    win32pipe.WaitNamedPipe(PIPE_NAME, 2000)
                except pywintypes.error:
                    time.sleep(CONNECT_RETRY_DELAY)

            else:
                raise IpcConnectionError(
                    f"Failed to connect to pipe: {e.strerror} (error {error_code})"
                ) from e


def _read_response(handle: int, timeout: int) -> bytes:
    """Read the response from the pipe."""
    data = b""
    deadline = time.monotonic() + timeout

    while True:
        if time.monotonic() >= deadline:
            raise IpcTimeoutError(
                f"No response from Revit within {timeout}s. "
                "Revit may be busy with a modal dialog."
            )
        try:
            hr, chunk = win32file.ReadFile(handle, BUFFER_SIZE)
            data += chunk
            if b"\n" in data:
                return data
        except pywintypes.error as e:
            if e.winerror == 109:  # ERROR_BROKEN_PIPE - server closed connection
                if data:
                    return data
                raise IpcError("Pipe closed by server before response was sent.") from e
            raise
