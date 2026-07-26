from __future__ import annotations

import argparse
import json
import sys

from polar_ble_tools.rec import RecDecodeError, decode_recording, decoder_status


def rec_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polar-ble rec")
    commands = parser.add_subparsers(dest="command", required=True)
    decode = commands.add_parser("decode")
    decode.add_argument("input")
    decode.add_argument("--output", required=True)
    decode.add_argument("--overwrite", action="store_true")
    decode.add_argument("--timeout", type=float)
    commands.add_parser("status")
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(decoder_status().__dict__, sort_keys=True))
        return 0
    try:
        report = decode_recording(
            args.input, args.output, overwrite=args.overwrite, timeout_seconds=args.timeout
        )
    except RecDecodeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "source": str(report.source_path),
                "output": str(report.destination_path),
                "record_count": report.record_count,
                "record_types": report.record_types,
                "sdk_commit": report.sdk_commit,
                "decoder_version": report.decoder_version,
                "warnings": report.warnings,
            },
            sort_keys=True,
        )
    )
    return 0
