# SoPoVis

**Soccer Positions Visualization** — Python library and desktop UI for exploring
football tracking data: three coordinated views (timeline control, tactical
position plot, pitch animation) on DFL Bundesliga XML feeds, with shape-graph
and tactical-role analytics.

Place DFL XML match triplets in `sample_Data/` locally (not included in the repo).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick start

```bash
sopovis                    # default match (Köln : Bayern)
sopovis DFL-MAT-J03WMX     # explicit match id
```

Or from Python:

```python
from sopovis import load_match, build_bundle
from sopovis.ui import MatchDesktopApp

state = load_match("sample_Data", "DFL-MAT-J03WMX")   # Köln : Bayern
bundle = build_bundle(state)                           # cached in .cache/
MatchDesktopApp(bundle, preset="tactical").run()
```

## Layout

| Path | Content |
|---|---|
| `src/sopovis/io` | DFL XML ingestion (floodlight-based) → `MatchState` |
| `src/sopovis/analytics` | Shape graph + tactical role inference |
| `src/sopovis/bundle` | `PrecomputedBundle` + disk cache |
| `src/sopovis/render` | Element system, `SceneRenderer`, built-in layers |
| `src/sopovis/ui` | `FrameCursor`, three views, `MatchDesktopApp` |
| `presets/` | YAML layer stacks (`tactical`, `broadcast`) |
| `tests/` | Smoke tests for CLI, desktop UI, and canvas helpers |

## Tests

```bash
pytest
```
