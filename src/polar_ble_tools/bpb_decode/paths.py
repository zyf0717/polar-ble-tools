from __future__ import annotations

from pathlib import Path, PurePosixPath

from polar_ble_tools.bpb_decode.models import BpbDecodeResult


def normalize_device_path(raw: str | Path) -> str:
    text = str(raw).replace("\\", "/").strip()
    if not text:
        raise ValueError("Device path is empty.")
    if not text.startswith("/"):
        text = f"/{text}"
    normalized = PurePosixPath(text).as_posix()
    if normalized == ".":
        raise ValueError("Device path is empty.")
    return normalized


def infer_device_path(local_path: Path) -> str | None:
    parts = local_path.parts
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == "files" and index + 1 < len(parts):
            return "/" + PurePosixPath(*parts[index + 1 :]).as_posix()
    if local_path.name.upper() in {"DEVICE.BPB", "SDLOGS.BPB"}:
        return f"/{local_path.name}"
    return None


def decoded_output_path(output_dir: str | Path, result: BpbDecodeResult) -> Path:
    root = Path(output_dir)
    if result.device_path is None:
        return root / f"{Path(result.local_path).name or 'unknown.BPB'}.json"
    parts = safe_device_path_parts(result.device_path)
    path = root.joinpath(*parts)
    return path.with_name(f"{path.name}.json")


def safe_device_path_parts(device_path: str) -> tuple[str, ...]:
    parts = PurePosixPath(normalize_device_path(device_path)).parts[1:]
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"invalid device path {device_path!r}")
    return tuple(parts)
