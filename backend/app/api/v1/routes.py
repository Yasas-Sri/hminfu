import re
import statistics
from datetime import UTC, datetime, time, timedelta
from typing import Annotated, Any, NoReturn

import pandas as pd
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError

from app.api.v1 import schemas as s
from app.config import Settings
from app.domain.models import Coverage
from app.services.analysis import AnalysisService, Params

router = APIRouter(prefix="/api/v1", responses={500: {"model": s.InternalError}})

# Contract limits (docs/API.md), not tunables.
MAX_RANGE = timedelta(days=62)
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def service(request: Request) -> AnalysisService:
    svc: AnalysisService = request.app.state.service
    return svc


def settings(request: Request) -> Settings:
    cfg: Settings = request.app.state.settings
    return cfg


def cacheable(response: Response) -> None:
    response.headers["Cache-Control"] = "public, max-age=3600"  # fixed snapshot


Svc = Annotated[AnalysisService, Depends(service)]


def analysis_params(
    request: Request,
    svc: Svc,
    cfg: Annotated[Settings, Depends(settings)],
    from_: Annotated[
        str | None,
        Query(alias="from", description="ISO-8601 with offset, whole hour. Default: window start"),
    ] = None,
    to: Annotated[
        str | None, Query(description="Exclusive end, ISO-8601 with offset. Default: window end")
    ] = None,
    cutoff: Annotated[
        str | None, Query(description="HH:MM, Europe/London on D−1. Default: 09:50")
    ] = None,
    lag_minutes: Annotated[int | None, Query(ge=0, le=180, description="Default: 0")] = None,
    aggregation: Annotated[s.Aggregation | None, Query(description="Default: point")] = None,
) -> Params:
    lo, hi = supported_range(svc)
    start = lo if from_ is None else _instant("from", from_)
    end = hi if to is None else _instant("to", to)
    # Range first, so an out-of-range `from` is blamed on `from`, not on a defaulted `to`.
    for name, value, t in (("from", from_, start), ("to", to, end)):
        if not lo <= t <= hi:
            _invalid(name, value, f"{name} must be within the snapshot range {_z(lo)} – {_z(hi)}")
    if start >= end:
        _invalid("to", to, "to must be after from")
    if end - start > MAX_RANGE:
        _invalid("to", to, "range must be at most 62 days")
    gate = cfg.gate_closure_local if cutoff is None else _hhmm(cutoff)
    lag = cfg.publish_lag_minutes if lag_minutes is None else lag_minutes
    request.state.params = {"from": _z(start), "to": _z(end), "cutoff": f"{gate:%H:%M}", "lag": lag}
    return Params(start, end, gate, lag, aggregation or cfg.aggregation)


Query_ = Annotated[Params, Depends(analysis_params)]


@router.get("/health")
def health(svc: Svc) -> s.HealthResponse:
    m = svc.snapshot.manifest
    return s.HealthResponse(
        status="ok",
        snapshot=s.SnapshotSummary(
            fetched_at=m["fetched_at"],
            forecast_rows=len(svc.snapshot.forecasts),
            actual_rows=len(svc.snapshot.actuals),
            conflicts=len(m["conflicts"]),
        ),
    )


@router.get("/meta")
def meta(svc: Svc, cfg: Annotated[Settings, Depends(settings)]) -> s.MetaResponse:
    lo, hi = supported_range(svc)
    per_day = list(svc.snapshot.manifest["publications_per_day"].values())
    window = s.TimeRange(from_=lo, to=hi)
    return s.MetaResponse(
        supported_target_range=window,
        default_window=window,
        defaults=s.Defaults(
            cutoff_local=f"{cfg.gate_closure_local:%H:%M}",
            publish_lag_minutes=cfg.publish_lag_minutes,
            aggregation=cfg.aggregation,
        ),
        data_as_of=svc.snapshot.manifest["fetched_at"],
        publications_per_day=s.PublicationsPerDay(
            min=min(per_day), median=statistics.median(per_day), max=max(per_day)
        ),
        sign_convention="error = forecast − actual (MW)",
    )


@router.get("/series", dependencies=[Depends(cacheable)])
def series(request: Request, svc: Svc, p: Query_) -> s.SeriesResponse:
    frame, cov, hit = svc.decisions(p)
    request.state.memo = _memo(hit)
    act = svc.actuals_halfhourly(p)
    return s.SeriesResponse(
        meta=_meta(svc, p, cov),
        points=[s.SeriesPoint(**r) for r in _records(frame)],
        actuals_halfhourly=[
            s.ActualHalfHour(start_time=t, actual_mw=v)
            for t, v in zip(act["start_time"], act["generation"], strict=True)
        ],
    )


@router.get("/metrics", dependencies=[Depends(cacheable)])
def metrics(request: Request, svc: Svc, p: Query_) -> s.MetricsResponse:
    m, cov, hit = svc.headline(p)
    request.state.memo = _memo(hit)
    q, over, under = m.error_quantiles_mw, m.largest_over_forecast, m.largest_under_forecast
    return s.MetricsResponse(
        meta=_meta(svc, p, cov),
        n=m.n,
        mae_mw=m.mae_mw,
        rmse_mw=m.rmse_mw,
        bias_mw=m.bias_mw,
        nmae=m.nmae,
        error_quantiles_mw=None if q is None else s.Quantiles(p10=q.p10, p50=q.p50, p90=q.p90),
        p90_over_forecast_mw=m.p90_over_forecast_mw,
        over_forecast_share=m.over_forecast_share,
        largest_over_forecast=None if over is None else s.Extreme(**vars(over)),
        largest_under_forecast=None if under is None else s.Extreme(**vars(under)),
    )


@router.get("/metrics/by-hour", dependencies=[Depends(cacheable)])
def metrics_by_hour(request: Request, svc: Svc, p: Query_) -> s.ByHourResponse:
    rows, cov, hit = svc.by_hour(p)
    request.state.memo = _memo(hit)
    return s.ByHourResponse(
        meta=_meta(svc, p, cov), rows=[s.ByHourRow(**r) for r in _records(rows)]
    )


@router.get("/metrics/by-horizon", dependencies=[Depends(cacheable)])
def metrics_by_horizon(
    request: Request,
    svc: Svc,
    p: Query_,
    bucket_hours: Annotated[int, Query(ge=1, le=24)] = 6,
) -> s.ByHorizonResponse:
    rows, used, hit = svc.by_horizon(p, bucket_hours)
    request.state.memo = _memo(hit)
    return s.ByHorizonResponse(
        meta=_meta(svc, p, None, cutoff_applied=False),
        bucket_hours=bucket_hours,
        rows_used=used,
        rows=[s.ByHorizonRow(**r) for r in _records(rows)],
    )


def supported_range(svc: AnalysisService) -> tuple[datetime, datetime]:
    target = svc.snapshot.manifest["ranges"]["target"]
    return _parse_z(target["from"]), _parse_z(target["to"])


def _meta(
    svc: AnalysisService, p: Params, cov: Coverage | None, cutoff_applied: bool = True
) -> s.Meta:
    return s.Meta(
        from_=p.start,
        to=p.end,
        cutoff_local=f"{p.gate_closure_local:%H:%M}",
        cutoff_timezone="Europe/London",
        publish_lag_minutes=p.lag_minutes,
        aggregation=p.aggregation,
        cutoff_applied=cutoff_applied,
        data_as_of=svc.snapshot.manifest["fetched_at"],
        coverage=None if cov is None else s.Coverage(**vars(cov)),
    )


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Rows as dicts with None for NaN/NaT (never 0) and Python datetimes for timestamps."""
    clean = df.astype(object).where(df.notna(), None)
    return [{str(k): v for k, v in row.items()} for row in clean.to_dict("records")]


def _instant(name: str, raw: str) -> datetime:
    try:
        t = datetime.fromisoformat(raw)
    except ValueError:
        _invalid(name, raw, f"{name} must be ISO-8601, e.g. 2026-01-02T00:00:00Z (encode + as %2B)")
    if t.tzinfo is None:
        _invalid(name, raw, f"{name} must include a timezone offset (e.g. Z)")
    utc = t.astimezone(UTC)
    if (utc.minute, utc.second, utc.microsecond) != (0, 0, 0):
        _invalid(name, raw, f"{name} must be a whole hour (e.g. 2026-01-02T00:00:00Z)")
    return utc


def _hhmm(raw: str) -> time:
    m = _HHMM.match(raw)
    if m is None:
        _invalid("cutoff", raw, "cutoff must be HH:MM between 00:00 and 23:59")
    return time(int(m.group(1)), int(m.group(2)))


def _invalid(name: str, value: object, msg: str) -> NoReturn:
    raise RequestValidationError(
        [{"type": "value_error", "loc": ("query", name), "msg": msg, "input": value}]
    )


def _parse_z(raw: str) -> datetime:
    return datetime.fromisoformat(raw).astimezone(UTC)


def _z(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _memo(hit: bool) -> str:
    return "hit" if hit else "miss"
