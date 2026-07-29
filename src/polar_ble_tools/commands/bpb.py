from __future__ import annotations

import argparse
import json
import sys

from polar_ble_tools.bpb_decode import (
    FAILED_STATUS,
    BpbManifestError,
    decode_bpb_file,
    decode_bpb_manifest,
    decode_passive_manifest,
)


def bpb_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polar-ble bpb")
    commands = parser.add_subparsers(dest="command", required=True)
    decode = commands.add_parser("decode")
    decode.add_argument("--path", required=True)
    decode.add_argument("--device-path")
    manifest = commands.add_parser("decode-manifest")
    manifest.add_argument("--manifest", required=True)
    manifest.add_argument("--output-dir")
    passive_manifest = commands.add_parser("decode-passive-manifest")
    passive_manifest.add_argument("--manifest", required=True)
    passive_manifest.add_argument("--output-dir")
    args = parser.parse_args(argv)
    try:
        if args.command == "decode":
            result = decode_bpb_file(args.path, device_path=args.device_path)
            print(json.dumps(result.to_jsonable(), sort_keys=True))
            return int(result.status == FAILED_STATUS)
        decoder = (
            decode_passive_manifest
            if args.command == "decode-passive-manifest"
            else decode_bpb_manifest
        )
        result = decoder(args.manifest, output_dir=args.output_dir)
        print(json.dumps(result.to_jsonable(), sort_keys=True))
        return int(not result.ok)
    except (BpbManifestError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
