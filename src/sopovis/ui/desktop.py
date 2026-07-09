"""MatchDesktopApp — standalone Tkinter shell for the three coordinated views.

Requires the TkAgg matplotlib backend (set in ``sopovis.main`` before import).

Figures are embedded in the Tk window *before* ``AppController`` draws so
control callbacks update the visible canvases (not a throwaway Agg canvas).
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import BUILTIN_PRESET_DIR, Preset, find_presets, load_preset
from sopovis.ui.app import AppController

_PLAY_INTERVAL_MS = 80  # step=2 at 80 ms ≈ real-time 25 fps
_SPEED_BY_LABEL = {"0.5×": 0.5, "1×": 1.0, "2×": 2.0, "4×": 4.0, "8×": 8.0}
_TEAM_OPTIONS = (("Home", "home"), ("Both", "both"), ("Away", "away"))
_DEFAULT_SMOOTHING = 150


class MatchDesktopApp:
    def __init__(
        self,
        bundle: PrecomputedBundle,
        preset: Preset | str | Path = "tactical",
        preset_dir: str | Path | None = None,
    ):
        self.bundle = bundle
        self.preset_dir = Path(preset_dir) if preset_dir else BUILTIN_PRESET_DIR
        self._presets = find_presets(self.preset_dir)
        if isinstance(preset, (str, Path)):
            preset = load_preset(self._presets.get(str(preset), preset))
        self.preset = preset

        self._playing = False
        self._play_step = 2
        self._play_after_id: str | None = None
        self._layer_vars: dict[str, tk.BooleanVar] = {}
        self._canvases: list[FigureCanvasTkAgg] = []
        self._syncing_slider = False
        self._t_max = bundle.total_frames - 1

        self.root = tk.Tk()
        title = (
            f"SoPoVis — {bundle.meta.home_team_name} "
            f"{bundle.meta.result} {bundle.meta.guest_team_name}"
        )
        self.root.title(title)
        self.root.minsize(1100, 720)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.fig_timeline = Figure(figsize=(12.0, 2.4))
        self.fig_plot = Figure(figsize=(6.4, 4.6))
        self.fig_pitch = Figure(figsize=(5.4, 4.6))
        for fig in (self.fig_timeline, self.fig_plot, self.fig_pitch):
            fig.canvas.toolbar_visible = False

        self._build_ui()
        self.app = AppController(
            bundle, preset, self.fig_timeline, self.fig_plot, self.fig_pitch
        )
        self._smoothing_var.set(float(self.app.position_plot.smoothing))
        self._rebuild_layer_toggles()
        self._refresh_all()

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        controls = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        controls.pack(fill="x")

        self._play_btn = ttk.Button(controls, text="Play", width=8, command=self._toggle_play)
        self._play_btn.pack(side="left", padx=(0, 8))

        self._frame_var = tk.DoubleVar(value=0.0)
        self._frame_scale = ttk.Scale(
            controls,
            from_=0.0,
            to=float(self._t_max),
            orient="horizontal",
            variable=self._frame_var,
            command=self._on_frame_scale,
        )
        self._frame_scale.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._frame_label = ttk.Label(controls, text="0", width=8, anchor="e")
        self._frame_label.pack(side="left", padx=(0, 8))

        ttk.Label(controls, text="Speed").pack(side="left")
        self._speed_var = tk.StringVar(value="1×")
        self._speed_menu = tk.OptionMenu(
            controls,
            self._speed_var,
            *_SPEED_BY_LABEL,
            command=self._on_speed_choice,
        )
        self._speed_menu.config(width=4, highlightthickness=0)
        self._speed_menu.pack(side="left", padx=(4, 12))

        ttk.Label(controls, text="Preset").pack(side="left")
        self._preset_var = tk.StringVar(value=self.preset.name)
        self._preset_menu = tk.OptionMenu(
            controls,
            self._preset_var,
            *sorted(self._presets),
            command=self._on_preset_choice,
        )
        self._preset_menu.config(width=10, highlightthickness=0)
        self._preset_menu.pack(side="left", padx=(4, 12))

        self._team_var = tk.StringVar(value="both")
        team_frame = ttk.Frame(controls)
        team_frame.pack(side="left", padx=(0, 8))
        ttk.Label(team_frame, text="Teams").pack(side="left", padx=(0, 4))
        for label, value in _TEAM_OPTIONS:
            tk.Radiobutton(
                team_frame,
                text=label,
                value=value,
                variable=self._team_var,
                command=self._on_team_focus,
                highlightthickness=0,
            ).pack(side="left", padx=(0, 2))

        ttk.Label(controls, text="Smooth").pack(side="left")
        self._smoothing_var = tk.DoubleVar(value=float(_DEFAULT_SMOOTHING))
        self._smoothing_scale = tk.Scale(
            controls,
            from_=5,
            to=600,
            orient="horizontal",
            variable=self._smoothing_var,
            length=120,
            showvalue=False,
            highlightthickness=0,
            command=self._on_smoothing_drag,
        )
        self._smoothing_scale.pack(side="left", padx=(4, 0))
        self._smoothing_scale.bind("<ButtonRelease-1>", self._on_smoothing_release)

        self._layer_frame = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        self._layer_frame.pack(fill="x")

        timeline_frame = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        timeline_frame.pack(fill="x")
        self._embed_figure(timeline_frame, self.fig_timeline)

        views = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        views.pack(fill="both", expand=True)

        plot_col = ttk.Frame(views)
        plot_col.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self._embed_figure(plot_col, self.fig_plot)

        pitch_col = ttk.Frame(views)
        pitch_col.pack(side="left", fill="both", expand=True, padx=(4, 0))
        self._embed_figure(pitch_col, self.fig_pitch)

    def _embed_figure(self, parent: ttk.Frame, fig: Figure) -> FigureCanvasTkAgg:
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._canvases.append(canvas)
        return canvas

    def _rebuild_layer_toggles(self) -> None:
        for child in self._layer_frame.winfo_children():
            child.destroy()
        self._layer_vars.clear()

        ttk.Label(self._layer_frame, text="Layers").pack(side="left", padx=(0, 8))
        for el in self.app.pitch.scene.elements:
            var = tk.BooleanVar(value=el.meta.enabled)
            self._layer_vars[el.meta.name] = var
            tk.Checkbutton(
                self._layer_frame,
                text=el.meta.name,
                variable=var,
                command=lambda name=el.meta.name, v=var: self._on_layer_toggle(name, v),
                highlightthickness=0,
            ).pack(side="left", padx=(0, 10))

    # -------------------------------------------------------------- callbacks

    def _on_scrub(self, t: int) -> None:
        t = max(0, min(int(t), self._t_max))
        self.app.timeline.on_scrub(t)
        self._syncing_slider = True
        self._frame_var.set(float(t))
        self._syncing_slider = False
        self._frame_label.config(text=str(t))
        self._refresh_all()

    def _on_frame_scale(self, value: str) -> None:
        if self._syncing_slider:
            return
        if self._playing:
            self._stop_play()
        self._on_scrub(int(float(value)))

    def _on_speed_choice(self, _choice: str) -> None:
        speed = _SPEED_BY_LABEL.get(self._speed_var.get(), 1.0)
        self.app.timeline.on_speed_change(speed)
        self._play_step = max(1, round(2 * speed))

    def _on_preset_choice(self, _choice: str) -> None:
        name = self._preset_var.get()
        if name not in self._presets:
            return
        preset = load_preset(self._presets[name])
        self.preset = preset
        self.app.on_preset_change(preset)
        self._rebuild_layer_toggles()
        self._refresh_all()

    def _on_team_focus(self) -> None:
        self.app.position_plot.set_team_focus(self._team_var.get())
        self._refresh_all()

    def _on_smoothing_drag(self, _value: str) -> None:
        # no-op during drag — full redraw is expensive on real matches
        return

    def _on_smoothing_release(self, _event=None) -> None:
        self.app.position_plot.set_smoothing(int(self._smoothing_var.get()))
        self._refresh_all()

    def _on_layer_toggle(self, name: str, var: tk.BooleanVar) -> None:
        self.app.toggle_layer(name, var.get())
        self._refresh_all()

    def _refresh_all(self) -> None:
        for canvas in self._canvases:
            canvas.draw()
        self.root.update_idletasks()

    def _toggle_play(self) -> None:
        if self._playing:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self) -> None:
        if self.app.cursor.t >= self._t_max:
            self._on_scrub(0)
        self._playing = True
        self._play_btn.config(text="Pause")
        self._play_tick()

    def _stop_play(self) -> None:
        self._playing = False
        self._play_btn.config(text="Play")
        if self._play_after_id is not None:
            self.root.after_cancel(self._play_after_id)
            self._play_after_id = None

    def _play_tick(self) -> None:
        if not self._playing:
            return
        t = self.app.cursor.t + self._play_step
        if t >= self.bundle.total_frames:
            self._on_scrub(self._t_max)
            self._stop_play()
            return
        self._on_scrub(t)
        self._play_after_id = self.root.after(_PLAY_INTERVAL_MS, self._play_tick)

    def _on_close(self) -> None:
        self._stop_play()
        for canvas in self._canvases:
            widget = canvas.get_tk_widget()
            widget.destroy()
        self.root.destroy()

    # ------------------------------------------------------------------- run

    def run(self) -> None:
        self.root.mainloop()
