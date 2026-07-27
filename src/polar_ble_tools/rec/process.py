"""Bounded sidecar process invocation and process-group cleanup."""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Mapping
from threading import Thread

from polar_ble_tools.rec.models import DecoderProtocolError, DecoderTimeoutError

MAX_DIAGNOSTIC_BYTES = 8_192
MAX_STATUS_BYTES = 8_192


def diagnostic(value: str | bytes | None) -> str:
    if not value:
        return "no diagnostic output"
    text = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
    return text.strip()[:MAX_DIAGNOSTIC_BYTES]


def _drain_stream(stream, limit: int, sink: list[bytes | bool]) -> None:
    payload = bytearray()
    exceeded = False
    while chunk := stream.read(8_192):
        remaining = limit - len(payload)
        if remaining > 0:
            payload.extend(chunk[:remaining])
        exceeded = exceeded or len(chunk) > remaining
    sink.extend((bytes(payload), exceeded))


def run_sidecar(
    command: list[str], *, environment: Mapping[str, str], timeout_seconds: float
) -> tuple[int, bytes, bytes]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        start_new_session=os.name == "posix",
    )
    assert process.stdout is not None and process.stderr is not None
    stdout: list[bytes | bool] = []
    stderr: list[bytes | bool] = []
    stdout_thread = Thread(
        target=_drain_stream,
        args=(process.stdout, MAX_STATUS_BYTES, stdout),
        daemon=True,
    )
    stderr_thread = Thread(
        target=_drain_stream,
        args=(process.stderr, MAX_DIAGNOSTIC_BYTES, stderr),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=2)
        raise DecoderTimeoutError("REC decoder timed out; retry with a larger timeout.") from exc
    finally:
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
    if stdout_thread.is_alive() or stderr_thread.is_alive():
        raise DecoderProtocolError("REC decoder did not close its diagnostic streams.")
    stdout_payload, stdout_exceeded = stdout
    stderr_payload, _ = stderr
    if stdout_exceeded:
        raise DecoderProtocolError("REC decoder status exceeded the maximum size.")
    return returncode, stdout_payload, stderr_payload


__all__ = ["diagnostic", "run_sidecar"]
