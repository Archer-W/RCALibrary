import os

# Load the co-located VoC analysis plugin before the app is imported, so the
# NetCare VoC template (which references voc_collect_trend) validates and runs.
os.environ.setdefault("RCA_PLUGINS", "usecases.netcare_voc")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from rcalibrary.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app)
