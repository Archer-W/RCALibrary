"""The plugin module listed in RCA_PLUGINS. Importing it registers everything.

Loaded by the framework at startup (before registries are built / templates
validated). It must not raise on import in environments where optional deps /
credentials are absent — guard those paths.
"""

import os

from rcalibrary import extensions

# 1) Analyzers self-register on import.
from . import analyzers  # noqa: F401

# 2) Real data source — only register when configured (otherwise stay on sample).
if os.getenv("SNOWFLAKE_ACCOUNT"):
    from .datasource_snowflake import SnowflakeProvider

    extensions.register_datasource(
        SnowflakeProvider(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
            database=os.environ["SNOWFLAKE_DATABASE"],
            schema=os.environ["SNOWFLAKE_SCHEMA"],
            role=os.getenv("SNOWFLAKE_ROLE"),
        )
    )

# 3) Authentication — opt in (the starter leaves the framework's anonymous
#    provider active so the demo is open). Uncomment to enable:
# from .auth_provider import ExampleAuthProvider
# extensions.set_auth_provider(ExampleAuthProvider())
