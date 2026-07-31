from pathlib import Path

WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"


def test_candidate_release_has_no_hardware_runner_dependency() -> None:
    workflow = (WORKFLOWS / "testpypi-candidate.yml").read_text()

    assert not (WORKFLOWS / "live-hardware.yml").exists()
    assert "live-gate" not in workflow
    assert "self-hosted" not in workflow
    assert "POLAR_BLE_LIVE_" not in workflow
    assert "protected-live-hardware" not in workflow
    assert "environment: sdk-contract" not in workflow
    assert not (WORKFLOWS / "sdk-contract.yml").exists()


def test_candidate_requires_merged_release_tree_and_consistent_metadata() -> None:
    workflow = (WORKFLOWS / "testpypi-candidate.yml").read_text()

    assert '"$GITHUB_REF_NAME" != "main"' in workflow
    assert "test ! -e AGENTS.md" in workflow
    assert "test ! -e specs" in workflow
    assert "RELEASE_NOTES.md" in workflow
    assert "CHANGELOG.md" in workflow
    assert "^## Unreleased$" in workflow


def test_sdk_free_workflows_run_only_sdk_free_contracts() -> None:
    workflow = (WORKFLOWS / "test.yml").read_text()

    assert "python -m pytest -q tests/unit tests/contracts" in workflow
    assert '".[dev,sdk]"' not in workflow
    assert "tests/sdk_contract" not in workflow
    assert "macos-latest" not in workflow
    assert "windows-latest" not in workflow
    candidate = (WORKFLOWS / "testpypi-candidate.yml").read_text()
    assert "python -m pytest -q tests/unit tests/contracts/test_protocol_contracts.py" in candidate
    assert '".[dev,sdk]"' not in candidate
    assert "tests/sdk_contract" not in candidate
    assert "polar-ble sdk install" not in candidate


def test_public_workflows_do_not_install_or_run_sdk_contracts() -> None:
    assert not (WORKFLOWS / "sdk-contract.yml").exists()
    for workflow in WORKFLOWS.glob("*.yml"):
        content = workflow.read_text()
        assert '".[dev,sdk]"' not in content
        assert "tests/sdk_contract" not in content
        assert "polar-ble sdk install" not in content


def test_pypi_release_promotes_the_successful_candidate_artifacts() -> None:
    workflow = (WORKFLOWS / "pypi-release.yml").read_text()

    assert "workflow_dispatch:" not in workflow
    assert "python -m build" not in workflow
    assert "git ls-remote --tags origin" in workflow
    assert '"${tag_ref}^{}"' in workflow
    assert "--workflow testpypi-candidate.yml" in workflow
    assert "--status success" in workflow
    assert "run_id=$run_id" in workflow
    assert '--name "distributions-${GITHUB_SHA}"' in workflow
    assert "Verify promoted distributions against TestPyPI" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
