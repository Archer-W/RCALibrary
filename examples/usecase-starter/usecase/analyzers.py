"""Example custom analyzer. Self-registers on import via @analyzer."""

from rcalibrary.analyzers import analyzer
from rcalibrary.analyzers.context import AnalysisContext, AnalysisResult


@analyzer("ran_kpi_correlation")
def ran_kpi_correlation(ctx: AnalysisContext) -> AnalysisResult:
    """Flag samples where BLER is high AND downlink throughput is low."""
    df = ctx.dataset
    bler_max = float(ctx.params.get("bler_max", 10))
    thpt_min = float(ctx.params.get("thpt_min", 5))
    bad = df[(df["bler"] > bler_max) & (df["dl_thpt_mbps"] < thpt_min)]
    return AnalysisResult(
        summary={"correlated_points": int(len(bad))},
        anomalies=[
            {
                "index": int(i),
                "column": "dl_thpt_mbps",
                "value": float(v),
                "severity": "high",
                "reason": f"BLER>{bler_max}% and throughput<{thpt_min}Mbps",
            }
            for i, v in bad["dl_thpt_mbps"].items()
        ],
        table=bad.to_dict("records"),
    )
