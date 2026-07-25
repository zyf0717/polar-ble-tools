from __future__ import annotations

PMD_SERVICE = "fb005c80-02e7-f387-1cad-8acd2d8df0c8"
PMD_CONTROL_POINT = "fb005c81-02e7-f387-1cad-8acd2d8df0c8"
PMD_DATA = "fb005c82-02e7-f387-1cad-8acd2d8df0c8"

PFTP_SERVICE = "0000feee-0000-1000-8000-00805f9b34fb"
PFTP_SERVICE_16BIT = "feee"
PFTP_MTU = "fb005c51-02e7-f387-1cad-8acd2d8df0c8"
PFTP_DEVICE_TO_HOST = "fb005c52-02e7-f387-1cad-8acd2d8df0c8"
PFTP_HOST_TO_DEVICE = "fb005c53-02e7-f387-1cad-8acd2d8df0c8"

PFTP_SERVICE_ALIASES = frozenset({PFTP_SERVICE, PFTP_SERVICE_16BIT})


def normalize_uuid(uuid: str) -> str:
    return uuid.lower()
