from __future__ import annotations

import argparse

from polar_ble_tools import doctor
from polar_ble_tools.commands.common import print_json


def doctor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="polar-ble doctor",
        description="Report core and optional local-schema readiness.",
    )
    parser.parse_args(argv)
    print_json(doctor().to_dict())
    return 0
