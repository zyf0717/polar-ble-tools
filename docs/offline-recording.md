# Offline recording

Offline recording control is available through an open device session. Query
the device before selecting a data type or settings; supported measurements and
settings vary by firmware.

```python
import asyncio

from polar_ble_tools.device import open_polar_device
from polar_ble_tools.polar.pmd import PolarDeviceDataType


async def record(mac_address: str) -> None:
    async with open_polar_device(mac_address) as device:
        control = device.services.offline_control
        available = await control.get_available_recording_types()
        if PolarDeviceDataType.ACC not in available:
            raise RuntimeError("Accelerometer offline recording is unavailable")
        settings = await control.request_full_recording_settings(PolarDeviceDataType.ACC)
        await control.start_recording(PolarDeviceDataType.ACC, settings)
        try:
            await asyncio.sleep(10)
        finally:
            await control.stop_recording(PolarDeviceDataType.ACC)


asyncio.run(record("AA:BB:CC:DD:EE:FF"))
```

Always stop a recording in `finally`. A stopped recording may take time to
appear through PFTP. Listing and collection are separate operations; use
`polar-ble raw` after the device has finalized its `.REC` file.

The control client also exposes recording status and trigger setup. Unsupported
measurement types and trigger combinations raise explicit PMD operation errors.
