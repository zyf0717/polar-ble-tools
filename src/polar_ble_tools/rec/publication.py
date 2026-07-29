"""Constrained destination preflight and atomic decoded-output publication."""

from __future__ import annotations

import os
from pathlib import Path

from polar_ble_tools.rec.models import DecoderProtocolError, RecordingDecodeError
from polar_ble_tools.rec.validation import validated_rows


def preflight_destination(source: Path, destination: Path, *, overwrite: bool) -> None:
    resolved_destination = destination.resolve(strict=False)
    if resolved_destination == source or (
        destination.exists() and os.path.samefile(source, destination)
    ):
        raise RecordingDecodeError("Output must differ from the source recording.")
    if destination.exists() and not overwrite:
        raise RecordingDecodeError(
            f"Output already exists: {destination}; pass overwrite=True to replace it."
        )
    if destination.exists() and overwrite:
        try:
            validated_rows(destination, None)
        except DecoderProtocolError as exc:
            raise RecordingDecodeError(
                "Overwrite requires an existing project-owned decoded JSONL output."
            ) from exc


def publish_decoded_output(temporary: Path, destination: Path, *, overwrite: bool) -> None:
    if overwrite:
        os.replace(temporary, destination)
        return
    try:
        os.link(temporary, destination)
    except FileExistsError as exc:
        raise RecordingDecodeError(
            f"Output already exists: {destination}; pass overwrite=True to replace it."
        ) from exc
    temporary.unlink()


__all__ = ["preflight_destination", "publish_decoded_output"]
