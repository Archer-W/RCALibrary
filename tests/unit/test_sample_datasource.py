import pytest

from rcalibrary.config import get_settings
from rcalibrary.datasources.base import DataPullRequest, NeutralFilter
from rcalibrary.datasources.sample import SampleDataProvider
from rcalibrary.errors import DataSourceError

NS = "ana.rca.generic-demo"


def provider():
    return SampleDataProvider(get_settings().samples_dir)


def test_fetch_with_filter():
    req = DataPullRequest(
        dataset="latency_timeseries",
        namespace=NS,
        filters=[NeutralFilter(column="node_id", op="eq", value="node-001")],
    )
    result = provider().fetch(req)
    assert result.row_count > 0
    assert "latency_ms" in result.columns
    assert set(result.frame["node_id"].unique()) == {"node-001"}


def test_column_projection():
    req = DataPullRequest(dataset="error_counts", namespace=NS, columns=["ts", "error_count"])
    result = provider().fetch(req)
    assert result.columns == ["ts", "error_count"]


def test_missing_dataset_raises():
    with pytest.raises(DataSourceError):
        provider().fetch(DataPullRequest(dataset="does_not_exist", namespace=NS))
