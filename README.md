# Wind Forecast Decision Explorer

> Pilot web app for a UK utility's day-ahead buying team: see the wind forecast that was available at gate closure,
> and how accurate those decision-time forecasts were, for purchase decisions made in January 2026.

**Live app:** TODO(human) · **API docs:** TODO(human)/api/v1/docs · **Video:** submitted via the form

<!-- Agent: do not replace TODO(human) markers with guesses. -->

## What it shows
- **Explorer:** for each hour, the latest wind forecast published before the day-ahead cutoff vs the actual outturn.
- **Accuracy:** MAE, bias, error quantiles, historical P90 over-forecast, by hour of day, by forecast horizon.

## Key assumptions (details in `docs/DECISIONS.md`)
- **Window (our reading of the brief):** decisions on 1–31 Jan 2026 mean delivery **2 Jan → 1 Feb 2026** (744 hours).
- **Cutoff:** 09:50 Europe/London on D−1 (N2EX-based default, adjustable).
- **Forecast availability:** raw `publishTime` used as availability time (lag 0, adjustable). See ADR-008 for the
  discrepancy with Elexon's published update schedule. Sensitivity below.
- **Error = forecast − actual (MW).** Positive = over-forecast (potential shortfall); negative = under-forecast
  (potential excess procurement).
- **Alignment:** hourly forecast vs the actual half-hour starting on the hour (`point`). `hourly_mean` is also reported.
- **Interpretation:** this measures forecast error, not the client's actual trades. Data covers wind as reported by
  Elexon (`FUELHH` WIND, `WINDFOR`) only. Snapshot fetched: TODO(human, from manifest.json).

## Headline results (January 2026 sample)
| Setting | MAE (MW) | Bias (MW) | Hours |
|---|---|---|---|
| lag 0, point | TODO | TODO | TODO |
| lag 60, point | TODO | TODO | TODO |
| lag 0, hourly_mean | TODO | TODO | TODO |

## How to run
**Docker (recommended)**
```bash
make up        # web: http://localhost:5173   API docs: http://localhost:8000/api/v1/docs
```
**Without Docker:** needs `uv` and Node 22 (`frontend/.nvmrc`). `make install`, then `make api` and `make web` in two terminals.
**Checks:** `make check` · **Refresh data:** `make ingest` · **Regenerate API types:** `make types`

## Repository structure
| Path | What it is |
|---|---|
| `backend/app/domain/` | Pure logic: target grid, cutoff time maths, forecast selection, alignment, metrics |
| `backend/app/data/` | Elexon client, validation (dedupe/conflicts/gaps), snapshot repository |
| `backend/app/services/` | Orchestrates data + domain for the API, with memoisation |
| `backend/app/api/v1/` | FastAPI routes and Pydantic schemas (the public contract) |
| `backend/scripts/` | `ingest.py` (Elexon → snapshot), `export_openapi.py` (schema for type generation) |
| `backend/data/snapshot/` | Committed data snapshot + `manifest.json` |
| `backend/tests/` | Unit, property and API tests |
| `frontend/src/features/` | Explorer and Accuracy views |
| `frontend/src/api/` | Generated API types + typed client |
| `backend/vercel.json`, `frontend/vercel.json` | Vercel config (two projects, see ADR-007) |
| `docs/` | Domain explainer, architecture, analysis definitions, API contract, ADRs, plan |

## Deployment
Two Vercel projects from this repo: backend (Root Directory `backend/`) and frontend (Root Directory `frontend/`,
rewriting `/api/*` to the backend). Cold start: TODO(human).

## AI tools used
TODO(human): state precisely which tools were used and for what (e.g. Claude Code for scaffolding, tests,
docs drafts), and how outputs were verified (golden tests from real Elexon data, manual review of domain logic).
