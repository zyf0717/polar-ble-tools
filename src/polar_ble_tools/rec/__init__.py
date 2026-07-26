"""Validated local decoding of Polar offline recording files."""

from polar_ble_tools.rec.api import (
    DecodeReport,
    DecoderManifestError,
    DecoderProtocolError,
    DecoderStatus,
    DecoderTimeoutError,
    DecoderUnavailableError,
    DecoderVerificationError,
    RecDecodeError,
    RecordingDecodeError,
    RecRecord,
    decode_recording,
    decoder_status,
    iter_decoded_records,
    verify_active_decoder,
)

__all__ = [
    "DecodeReport",
    "DecoderManifestError",
    "DecoderProtocolError",
    "DecoderStatus",
    "DecoderTimeoutError",
    "DecoderUnavailableError",
    "DecoderVerificationError",
    "RecDecodeError",
    "RecRecord",
    "RecordingDecodeError",
    "decode_recording",
    "decoder_status",
    "iter_decoded_records",
    "verify_active_decoder",
]
