# polar-ble-tools 0.1.1

`0.1.1` provides Linux/BlueZ tooling for BLE discovery and pairing, PMD and
PFTP operations, offline recording control, raw `.REC` retrieval, passive
`.BPB` retrieval, FTU setup, guarded cleanup, and BPB decoding with optional
locally generated schemas.

The release supports Python 3.11 through 3.14. Controlled hardware validation
covers Polar Loop Gen 2. Structured `.REC` decoding is not included.

The distribution does not include the Polar BLE SDK, Polar SDK schema source
files, or artefacts generated from those files. Users of SDK-assisted
functionality obtain and license the SDK separately.
