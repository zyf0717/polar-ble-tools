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
    assert "environment: sdk-contract" not in (WORKFLOWS / "sdk-contract.yml").read_text()


def test_sdk_workflows_clean_sdk_owned_paths_without_requiring_an_empty_app_root() -> None:
    for workflow_name in ("sdk-contract.yml", "testpypi-candidate.yml"):
        workflow = (WORKFLOWS / workflow_name).read_text()

        assert 'test ! -e "$XDG_DATA_HOME/polar-ble-tools/sdk/polar"' in workflow
        assert 'test ! -e "$XDG_DATA_HOME/polar-ble-tools/generated/polar"' in workflow
        assert 'test ! -e "$XDG_DATA_HOME/polar-ble-tools/active-sdk.json"' in workflow
        assert 'test ! -e "$XDG_DATA_HOME/polar-ble-tools"' not in workflow


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
