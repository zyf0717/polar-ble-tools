from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.schemas.requirements import requirements_for
from polar_ble_tools.sdk_tools.downloader import OFFICIAL_SDK_URL
from polar_ble_tools.sdk_tools.generator import GENERATED_MANIFEST
from polar_ble_tools.sdk_tools.verifier import SchemaVerificationError, verify_schemas

COMMIT = "a" * 40


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[SdkCache, Path, dict[str, object]]:
    # The optional compiler must not be required to verify a completed cache.
    from importlib.metadata import PackageNotFoundError

    import polar_ble_tools.sdk_tools.verifier as verifier

    def no_compiler(_distribution: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(verifier, "version", no_compiler)
    cache = SdkCache(tmp_path / "cache")
    source = cache.sdk_path(COMMIT) / "source"
    source.mkdir(parents=True)
    (cache.sdk_path(COMMIT) / "download-manifest.json").write_text(
        json.dumps(
            {
                "format_version": 2,
                "source_repository": OFFICIAL_SDK_URL,
                "requested_ref": COMMIT,
                "resolved_commit": COMMIT,
                "extraction_method": "git archive",
            }
        ),
        encoding="utf-8",
    )
    cache.active_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cache.active_manifest_path.write_text(json.dumps({"resolved_commit": COMMIT}), encoding="utf-8")

    root = cache.generated_path(COMMIT)
    python_root = root / "python"
    python_root.mkdir(parents=True)
    requirement = requirements_for("setup", "passive", "bpb")
    for module in requirement.modules:
        (python_root / f"{module}.py").write_text("VALUE = 1\n", encoding="utf-8")
    descriptor = root / "descriptor.desc"
    descriptor.write_bytes(b"synthetic descriptor")
    generated_files = sorted(
        path.relative_to(root).as_posix() for path in python_root.glob("*_pb2.py")
    )
    manifest: dict[str, object] = {
        "format_version": 2,
        "source_repository": OFFICIAL_SDK_URL,
        "requested_ref": COMMIT,
        "resolved_commit": COMMIT,
        "descriptor_sha256": _sha256(descriptor),
        "required_features": ["setup", "passive", "bpb"],
        "generated_files": generated_files,
        "generated_file_hashes": {name: _sha256(root / name) for name in generated_files},
        "dependency_closure": ["synthetic.proto"],
        "resolved_symbols": {symbol: "synthetic.proto" for symbol in requirement.symbols},
        "toolchain": {
            "grpcio_tools": "not-required-at-runtime",
            "protoc": "not-required-at-runtime",
            "protobuf": __import__("google.protobuf").protobuf.__version__,
            "python": sys.version.split()[0],
        },
    }
    (root / GENERATED_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return cache, root, manifest


def _write_manifest(root: Path, manifest: dict[str, object]) -> None:
    (root / GENERATED_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")


def test_verifier_accepts_a_complete_synthetic_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, root, _manifest = _write_cache(tmp_path, monkeypatch)

    assert verify_schemas(cache=cache) == root / "python"
    assert all(
        not (
            (module_file := getattr(sys.modules.get(module), "__file__", None))
            and Path(module_file).resolve().is_relative_to((root / "python").resolve())
        )
        for module in requirements_for("setup", "passive", "bpb").modules
    )


def test_verifier_rejects_corrupt_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, root, _manifest = _write_cache(tmp_path, monkeypatch)
    (root / "descriptor.desc").write_bytes(b"corrupt")

    with pytest.raises(SchemaVerificationError, match="descriptor hash"):
        verify_schemas(cache=cache)


def test_verifier_rejects_invalid_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache, root, _manifest = _write_cache(tmp_path, monkeypatch)
    (root / GENERATED_MANIFEST).write_text("not-json", encoding="utf-8")

    with pytest.raises(SchemaVerificationError, match="Invalid generated schema manifest"):
        verify_schemas(cache=cache)


def test_verifier_rejects_corrupt_generated_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, root, _manifest = _write_cache(tmp_path, monkeypatch)
    (root / "python" / "types_pb2.py").write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(SchemaVerificationError, match="cache is corrupt"):
        verify_schemas(cache=cache)


def test_verifier_rejects_missing_symbols(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache, root, manifest = _write_cache(tmp_path, monkeypatch)
    manifest["resolved_symbols"] = {}
    _write_manifest(root, manifest)

    with pytest.raises(SchemaVerificationError, match="missing required symbols"):
        verify_schemas(cache=cache)


def test_verifier_rejects_nondeterministic_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, root, manifest = _write_cache(tmp_path, monkeypatch)
    manifest["dependency_closure"] = ["synthetic.proto", "synthetic.proto"]
    _write_manifest(root, manifest)

    with pytest.raises(SchemaVerificationError, match="not deterministic"):
        verify_schemas(cache=cache)


def test_verifier_rejects_source_metadata_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, _root, _manifest = _write_cache(tmp_path, monkeypatch)
    (cache.sdk_path(COMMIT) / "download-manifest.json").write_text(
        json.dumps(
            {
                "source_repository": OFFICIAL_SDK_URL,
                "requested_ref": "different-source",
                "resolved_commit": COMMIT,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SchemaVerificationError, match="source metadata"):
        verify_schemas(cache=cache)


def test_verifier_rejects_incompatible_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, root, manifest = _write_cache(tmp_path, monkeypatch)
    manifest["toolchain"] = {**manifest["toolchain"], "python": "0.0.0"}
    _write_manifest(root, manifest)

    with pytest.raises(SchemaVerificationError, match="toolchain is incompatible"):
        verify_schemas(cache=cache)
