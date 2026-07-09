"""CLI entry point — load a match and open the desktop app."""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

DEFAULT_MATCH = "DFL-MAT-J03WMX"
DATA_DIR = Path(__file__).resolve().parents[2] / "sample_Data"
PRESET = "tactical"
CACHE_DIR = ".cache"


def match_id_from_argv(argv: list[str] | None = None) -> str:
    args = argv if argv is not None else sys.argv[1:]
    return args[0] if args else DEFAULT_MATCH


def _log(msg: str) -> None:
    print(msg, flush=True)


def _elapsed(t0: float) -> str:
    return f"{time.perf_counter() - t0:.1f}s"


def main(argv: list[str] | None = None) -> None:
    import matplotlib

    matplotlib.use("TkAgg")

    # floodlight warns on out-of-range gameclock values in some DFL feeds
    warnings.filterwarnings(
        "ignore",
        message="The 'gameclock' column does not match",
        category=UserWarning,
    )

    from sopovis import build_bundle, load_match
    from sopovis.ui.desktop import MatchDesktopApp

    mid = match_id_from_argv(argv)
    verbose = sys.stdout.isatty()
    t_total = time.perf_counter()

    _log(f"SoPoVis — {mid}")
    _log(f"[1/3] Loading DFL XML from {DATA_DIR} …")
    t0 = time.perf_counter()
    state = load_match(DATA_DIR, mid)
    _log(
        f"      {state.meta.home_team_name} {state.meta.result} "
        f"{state.meta.guest_team_name}"
    )
    _log(
        f"      {state.total_frames:,} frames @ {state.frame_rate:g} fps · "
        f"{len(state.player_ids)} players · {len(state.events):,} events · "
        f"{_elapsed(t0)}"
    )

    _log("[2/3] Building analytics (shape graphs + tactical roles) …")
    t1 = time.perf_counter()
    bundle = build_bundle(
        state,
        cache_dir=CACHE_DIR,
        progress=verbose,
        verbose=verbose,
    )
    _log(
        f"      {bundle.total_analytics_frames:,} analytics frames · {_elapsed(t1)}"
    )

    _log(f"[3/3] Opening desktop UI (preset: {PRESET}) …")
    app = MatchDesktopApp(bundle, preset=PRESET)
    _log(f"Ready in {_elapsed(t_total)} — close the window to exit.")
    app.run()


if __name__ == "__main__":
    main()
