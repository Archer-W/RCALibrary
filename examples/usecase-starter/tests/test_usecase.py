"""Example use-case test. Run with the framework's deps installed:

    PYTHONPATH="framework/backend:." \
    RCA_TEMPLATES_DIR=./templates RCA_SAMPLES_DIR=./data/samples \
    RCA_PLUGINS=usecase.plugins pytest
"""

import os

os.environ.setdefault("RCA_TEMPLATES_DIR", "./templates")
os.environ.setdefault("RCA_SAMPLES_DIR", "./data/samples")
os.environ.setdefault("RCA_PLUGINS", "usecase.plugins")

from fastapi.testclient import TestClient  # noqa: E402
from rcalibrary.main import app  # noqa: E402

client = TestClient(app)


def test_problem_and_template_appear():
    problems = client.get("/api/problems").json()
    assert any(p["id"] == "ran.throughput-degradation" for p in problems)


def test_template_runs_and_flags_degradation():
    r = client.post(
        "/api/templates/ran.cell-throughput/run",
        json={"inputs": {"cell_id": "C-001", "lookback_hours": 24, "prb_util_threshold": 85}},
    )
    assert r.status_code == 200
    report = r.json()["report"]
    assert report["summary"]["total_anomalies"] >= 1
