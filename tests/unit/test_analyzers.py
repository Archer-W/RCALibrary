import pandas as pd
import pytest

from rcalibrary.analyzers.builtins import passthrough, threshold_breach, zscore_anomaly
from rcalibrary.analyzers.context import AnalysisContext
from rcalibrary.errors import AnalysisError


def ctx(df, **params):
    return AnalysisContext(dataset=df, params=params, inputs={})


def test_threshold_breach_flags_rows():
    df = pd.DataFrame({"v": [1, 5, 10, 2]})
    res = threshold_breach(ctx(df, column="v", op="gt", threshold=4, severity="high"))
    assert res.summary["breach_count"] == 2
    assert len(res.anomalies) == 2
    assert all(a["severity"] == "high" for a in res.anomalies)
    assert any(a["type"] == "hline" for a in res.annotations)
    assert len(res.table) == 2


def test_threshold_breach_missing_column_raises():
    df = pd.DataFrame({"v": [1]})
    with pytest.raises(AnalysisError):
        threshold_breach(ctx(df, column="nope", threshold=1))


def test_zscore_anomaly_flags_outlier():
    df = pd.DataFrame({"v": [1, 1, 1, 1, 1, 50]})
    res = zscore_anomaly(ctx(df, column="v", z_threshold=2.0))
    assert res.summary["anomaly_count"] >= 1
    assert any(a["value"] == 50 for a in res.anomalies)


def test_passthrough_counts_rows():
    df = pd.DataFrame({"v": [1, 2, 3]})
    res = passthrough(ctx(df))
    assert res.summary["row_count"] == 3
    assert res.anomalies == []
