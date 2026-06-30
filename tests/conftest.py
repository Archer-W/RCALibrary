import os
import tempfile

# Load the co-located VoC analysis plugin before the app is imported, so the
# NetCare VoC template (which references voc_collect_trend) validates and runs.
os.environ.setdefault("RCA_PLUGINS", "usecases.netcare_voc")
# Isolate the saved-report cache to a throwaway dir so /run tests are deterministic
# (never auto-load a previously-saved report) and never touch the real data/cache.
os.environ.setdefault("RCA_REPORT_CACHE_DIR", tempfile.mkdtemp(prefix="rca-test-cache-"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from rcalibrary.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app)
