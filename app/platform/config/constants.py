from dataclasses import dataclass


@dataclass(frozen=True)
class VersionConstants:
    contract_version: str = "1.0.0"
    app_version: str = "0.1.0-mvp"
    schema_version: int = 1
    build_metadata: str = "local-mvp"


VERSION_CONSTANTS = VersionConstants()
