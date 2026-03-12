"""
Registry provider factory.

Selects and constructs the correct ToolRegistryProvider implementation
based on the REGISTRY_FLAVOR environment variable.

  REGISTRY_FLAVOR=postgres  → PostgresRegistryProvider  (default)

To add a new flavor:
  1. Create registry/<flavor>_registry.py implementing ToolRegistryProvider
  2. Add the import and case below — no other files need to change.
"""

import os
from registry.base import ToolRegistryProvider


def build_registry_provider() -> ToolRegistryProvider:
    flavor = os.getenv("REGISTRY_FLAVOR", "postgres").lower()

    if flavor == "postgres":
        from registry.postgres_registry import PostgresRegistryProvider
        pg_dsn = (
            f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
            f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
        )
        return PostgresRegistryProvider(
            dsn=pg_dsn,
            reconnect_delay_seconds=int(os.getenv("REGISTRY_RECONNECT_DELAY", "2")),
        )

    raise ValueError(
        f"Unknown REGISTRY_FLAVOR: '{flavor}'. "
        f"To add a new flavor, implement ToolRegistryProvider and register it here."
    )
