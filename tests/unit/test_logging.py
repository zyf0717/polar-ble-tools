from polar_ble_tools.logging import get_hub_logger, log_event


def test_get_hub_logger_creates_component_log_and_formats_fields(tmp_path) -> None:
    logger = get_hub_logger("hub.connect", tmp_path)

    log_event(logger, "connect_start", mac="AA:BB:CC:DD:EE:FF", attempt=1)

    log_path = tmp_path / "hub_connect.log"
    assert log_path.exists()
    contents = log_path.read_text(encoding="utf-8")
    assert "connect_start" in contents
    assert "attempt=1" in contents
    assert "mac=AA:BB:CC:DD:EE:FF" in contents
