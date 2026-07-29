"""Validated local decoding of Polar offline recording files."""

from polar_ble_tools.rec.api import (
    decode_recording,
    decoder_status,
    iter_decoded_records,
    verify_active_decoder,
)
from polar_ble_tools.rec.models import (
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
    UnsupportedRecordingError,
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
    "UnsupportedRecordingError",
    "decode_recording",
    "decoder_status",
    "iter_decoded_records",
    "verify_active_decoder",
]
