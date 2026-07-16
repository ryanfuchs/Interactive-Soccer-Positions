"""MatchDesktopApp — standalone Tkinter shell for the three coordinated views.

Requires the TkAgg matplotlib backend (set in ``sopovis.main`` before import).

Figures are embedded in the Tk window *before* ``AppController`` draws so
control callbacks update the visible canvases (not a throwaway Agg canvas).
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Callable

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from sopovis.bundle.bundle import PrecomputedBundle
from sopovis.config.presets import BUILTIN_PRESET_DIR, Preset, find_presets, load_preset
from sopovis.config.settings import (
    DEFAULT_SETTINGS_PATH,
    UserSettings,
    load_settings,
    save_settings,
)
from sopovis.model.sections import SECTION_ORDER, section_display_name
from sopovis.ui.app import AppController

# Playback: step=2 every 80 ms ≈ real-time 25 fps (see UserSettings.play_interval_ms).
_SPEED_BY_LABEL = {"0.5×": 0.5, "1×": 1.0, "2×": 2.0, "4×": 4.0, "8×": 8.0}
_TEAM_OPTIONS = (("Home", "home"), ("Both", "both"), ("Away", "away"))
_POSSESSION_OPTIONS = (
    ("All", "all"),
    ("Home ball", "home"),
    ("Away ball", "away"),
    ("Contested", "contested"),
)


class _Tooltip:
    """Simple hover tooltip; ``text`` may be a str or a zero-arg callable."""

    def __init__(self, widget: tk.Widget, text: str | Callable[[], str]):
        self.widget = widget
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _resolve(self) -> str:
        return self._text() if callable(self._text) else self._text

    def _show(self, _event=None) -> None:
        if self._tip is not None:
            return
        text = self._resolve()
        self._tip = tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_attributes("-topmost", True)
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        tip.wm_geometry(f"+{x}+{y}")
        ttk.Label(
            tip,
            text=text,
            relief="solid",
            padding=(6, 3),
            background="#ffffe0",
        ).pack()

    def _hide(self, _event=None) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


class MatchDesktopApp:
    def __init__(
        self,
        bundle: PrecomputedBundle,
        preset: Preset | str | Path = "tactical",
        preset_dir: str | Path | None = None,
        settings: UserSettings | None = None,
    ):
        self.bundle = bundle
        self.settings = settings or load_settings()
        self.preset_dir = Path(preset_dir) if preset_dir else BUILTIN_PRESET_DIR
        self._presets = find_presets(self.preset_dir)
        if isinstance(preset, (str, Path)):
            preset = load_preset(self._presets.get(str(preset), preset))
        self.preset = preset

        self._playing = False
        self._play_step = max(1, round(2 * self.settings.default_playback_speed))
        self._play_after_id: str | None = None
        self._layer_vars: dict[str, tk.BooleanVar] = {}
        self._canvases: list[FigureCanvasTkAgg] = []
        self._syncing_slider = False
        self._t0 = 0
        self._t_max = bundle.total_frames - 1
        self._period_keys: dict[str, str | None] = {"All": None}

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
        self.fig_pitch = Figure(figsize=(4.2, 5.6))
        for fig in (self.fig_timeline, self.fig_plot, self.fig_pitch):
            fig.canvas.toolbar_visible = False

        self._build_ui()
        self.app = AppController(
            bundle,
            preset,
            self.fig_timeline,
            self.fig_plot,
            self.fig_pitch,
            settings=self.settings,
        )
        self.app.on_view_changed.append(self._on_view_changed)
        self._resolution_var.set(float(self.app.position_plot.resolution))
        self._rebuild_layer_toggles()
        self._refresh_all()

    # ------------------------------------------------------------------ build
    #
    # Controls live next to the view they affect (proximity grouping):
    #   app bar   — match-wide state: preset, period, reset zoom
    #   timeline  — playback (play / scrub / speed) + timeline layer menu
    #   plot      — filters that recolor the heatmap (teams / possession / detail)
    #   pitch     — orientation + pitch layer menu

    def _build_ui(self) -> None:
        app_bar = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        app_bar.pack(fill="x")

        ttk.Label(app_bar, text="Preset").pack(side="left")
        self._preset_var = tk.StringVar(value=self.preset.name)
        self._preset_menu = tk.OptionMenu(
            app_bar,
            self._preset_var,
            *sorted(self._presets),
            command=self._on_preset_choice,
        )
        self._preset_menu.config(width=10, highlightthickness=0)
        self._preset_menu.pack(side="left", padx=(4, 16))
        _Tooltip(self._preset_menu, "Visual style: layer stack for pitch and timeline")

        ttk.Label(app_bar, text="Period").pack(side="left")
        self._period_keys = {"All": None}
        for key in SECTION_ORDER:
            if key in self.bundle.section_ranges:
                self._period_keys[section_display_name(key)] = key
        for key in self.bundle.section_ranges:
            label = section_display_name(key)
            if label not in self._period_keys:
                self._period_keys[label] = key
        self._period_var = tk.StringVar(value="All")
        self._period_menu = tk.OptionMenu(
            app_bar,
            self._period_var,
            *self._period_keys.keys(),
            command=self._on_period_choice,
        )
        self._period_menu.config(width=10, highlightthickness=0)
        self._period_menu.pack(side="left", padx=(4, 16))
        _Tooltip(self._period_menu, "Restrict all views to one match period")

        self._reset_zoom_btn = ttk.Button(
            app_bar, text="Reset zoom", width=10, command=self._on_reset_zoom
        )
        self._reset_zoom_btn.pack(side="left")
        _Tooltip(
            self._reset_zoom_btn,
            "Clear time zoom (or double-click the timeline / position plot)",
        )

        self._settings_dialog: tk.Toplevel | None = None
        ttk.Style(self.root).configure("Gear.TButton", padding=(2, 1))
        self._settings_btn = ttk.Button(
            app_bar,
            text="⚙",
            width=2,
            style="Gear.TButton",
            command=self._open_settings_dialog,
        )
        self._settings_btn.pack(side="right")
        _Tooltip(self._settings_btn, "Settings: save or reset startup defaults")

        # ------------------------------------------------------- timeline row
        timeline_frame = ttk.Labelframe(self.root, text="Timeline", padding=(6, 2, 6, 4))
        timeline_frame.pack(fill="x", padx=8, pady=(0, 4))

        timeline_bar = ttk.Frame(timeline_frame)
        timeline_bar.pack(fill="x", pady=(0, 2))

        self._play_btn = ttk.Button(timeline_bar, text="Play", width=8, command=self._toggle_play)
        self._play_btn.pack(side="left", padx=(0, 8))

        self._frame_var = tk.DoubleVar(value=0.0)
        self._frame_scale = ttk.Scale(
            timeline_bar,
            from_=0.0,
            to=float(self._t_max),
            orient="horizontal",
            variable=self._frame_var,
            command=self._on_frame_scale,
        )
        self._frame_scale.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._frame_label = ttk.Label(timeline_bar, text="0", width=8, anchor="e")
        self._frame_label.pack(side="left", padx=(0, 8))
        _Tooltip(self._frame_label, "Current tracking frame")

        ttk.Label(timeline_bar, text="Speed").pack(side="left")
        self._speed_var = tk.StringVar(value=self._speed_label(self.settings.default_playback_speed))
        self._speed_menu = tk.OptionMenu(
            timeline_bar,
            self._speed_var,
            *_SPEED_BY_LABEL,
            command=self._on_speed_choice,
        )
        self._speed_menu.config(width=4, highlightthickness=0)
        self._speed_menu.pack(side="left", padx=(4, 8))

        self._timeline_layers_btn, self._timeline_layers_menu = self._make_layer_menu(
            timeline_bar
        )
        self._timeline_layers_btn.pack(side="left")
        _Tooltip(self._timeline_layers_btn, "Show / hide timeline overlays")

        self._embed_figure(timeline_frame, self.fig_timeline)

        # ------------------------------------------------------- lower views
        views = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        views.pack(fill="both", expand=True)

        plot_col = ttk.Labelframe(views, text="Tactical positions", padding=(6, 2, 6, 4))
        plot_col.pack(side="left", fill="both", expand=True, padx=(0, 4))

        plot_bar = ttk.Frame(plot_col)
        plot_bar.pack(fill="x", pady=(0, 2))

        self._team_var = tk.StringVar(value=self.settings.default_team_focus)
        ttk.Label(plot_bar, text="Teams").pack(side="left", padx=(0, 4))
        for label, value in _TEAM_OPTIONS:
            ttk.Radiobutton(
                plot_bar,
                text=label,
                value=value,
                variable=self._team_var,
                command=self._on_team_focus,
            ).pack(side="left", padx=(0, 4))

        self._ball_in_play_var = tk.BooleanVar(value=self.settings.default_ball_in_play)
        in_play = ttk.Checkbutton(
            plot_bar,
            text="In play",
            variable=self._ball_in_play_var,
            command=self._on_ball_in_play,
        )
        in_play.pack(side="left", padx=(8, 8))
        _Tooltip(in_play, "Blank time bins where the ball is out of play")

        ttk.Label(plot_bar, text="Possession").pack(side="left")
        self._possession_keys = {label: value for label, value in _POSSESSION_OPTIONS}
        self._possession_var = tk.StringVar(
            value=self._possession_label(self.settings.default_possession_filter)
        )
        self._possession_menu = tk.OptionMenu(
            plot_bar,
            self._possession_var,
            *[label for label, _ in _POSSESSION_OPTIONS],
            command=self._on_possession_choice,
        )
        self._possession_menu.config(width=9, highlightthickness=0)
        self._possession_menu.pack(side="left", padx=(4, 8))
        _Tooltip(self._possession_menu, "Blank time bins that don't match this possession")

        ttk.Label(plot_bar, text="Resolution").pack(side="left")
        self._resolution_var = tk.DoubleVar(value=float(self.settings.default_resolution))
        self._resolution_scale = tk.Scale(
            plot_bar,
            from_=self.settings.min_resolution,
            to=self.settings.max_resolution,
            orient="horizontal",
            variable=self._resolution_var,
            length=110,
            showvalue=False,
            highlightthickness=0,
            command=self._on_resolution_drag,
        )
        self._resolution_scale.pack(side="left", padx=(4, 0))
        self._resolution_scale.bind("<ButtonRelease-1>", self._on_resolution_release)
        _Tooltip(self._resolution_scale, "Time-bin width of the role heatmap")

        self._position_layers_btn, self._position_layers_menu = self._make_layer_menu(plot_bar)
        self._position_layers_btn.pack(side="left", padx=(8, 0))
        _Tooltip(self._position_layers_btn, "Show / hide position overlays")

        self._embed_figure(plot_col, self.fig_plot)

        pitch_col = ttk.Labelframe(views, text="Pitch", padding=(6, 2, 6, 4))
        pitch_col.pack(side="left", fill="both", expand=True, padx=(4, 0))

        pitch_bar = ttk.Frame(pitch_col)
        pitch_bar.pack(fill="x", pady=(0, 2))

        self._pitch_layers_btn, self._pitch_layers_menu = self._make_layer_menu(pitch_bar)
        self._pitch_layers_btn.pack(side="left")
        _Tooltip(self._pitch_layers_btn, "Show / hide pitch overlays")

        self._home_bottom_var = tk.BooleanVar(value=self.settings.default_home_at_bottom)
        self._orient_btn = ttk.Button(
            pitch_bar,
            text="⇅",
            width=3,
            command=self._on_orientation_toggle,
        )
        self._orient_btn.pack(side="right")
        _Tooltip(
            self._orient_btn,
            lambda: (
                "Home at bottom of pitch — click to swap"
                if self._home_bottom_var.get()
                else "Away at bottom of pitch — click to swap"
            ),
        )
        self._embed_figure(pitch_col, self.fig_pitch)

    @staticmethod
    def _speed_label(speed: float) -> str:
        """Menu label for a playback-speed multiplier (nearest match, else 1×)."""
        for label, value in _SPEED_BY_LABEL.items():
            if abs(value - speed) < 1e-6:
                return label
        return "1×"

    def _possession_label(self, value: str) -> str:
        """Menu label for a possession-filter value (falls back to 'All')."""
        for label, val in _POSSESSION_OPTIONS:
            if val == value:
                return label
        return "All"

    def _make_layer_menu(self, parent: ttk.Frame) -> tuple[ttk.Menubutton, tk.Menu]:
        button = ttk.Menubutton(parent, text="Layers")
        menu = tk.Menu(button, tearoff=0)
        button["menu"] = menu
        return button, menu

    def _embed_figure(self, parent: ttk.Frame, fig: Figure) -> FigureCanvasTkAgg:
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._canvases.append(canvas)
        return canvas

    def _rebuild_layer_toggles(self) -> None:
        self._pitch_layers_menu.delete(0, "end")
        self._timeline_layers_menu.delete(0, "end")
        self._position_layers_menu.delete(0, "end")
        self._layer_vars.clear()

        for el in self.app.pitch.scene.elements:
            var = tk.BooleanVar(value=el.meta.enabled)
            self._layer_vars[el.meta.name] = var
            self._pitch_layers_menu.add_checkbutton(
                label=el.meta.ui_label(),
                variable=var,
                command=lambda name=el.meta.name, v=var: self._on_layer_toggle(name, v),
            )

        for el in self.app.timeline.elements:
            var = tk.BooleanVar(value=el.meta.enabled)
            self._layer_vars[f"timeline:{el.meta.name}"] = var
            self._timeline_layers_menu.add_checkbutton(
                label=el.meta.ui_label(),
                variable=var,
                command=lambda name=el.meta.name, v=var: self._on_timeline_layer_toggle(name, v),
            )

        for el in self.app.position_plot.stack.elements:
            var = tk.BooleanVar(value=el.meta.enabled)
            self._layer_vars[f"position:{el.meta.name}"] = var
            self._position_layers_menu.add_checkbutton(
                label=el.meta.ui_label(),
                variable=var,
                command=lambda name=el.meta.name, v=var: self._on_position_layer_toggle(name, v),
            )

    def _apply_time_window(self) -> None:
        self._t0, t1 = self.app.view_range.limits()
        self._t_max = max(self._t0, t1 - 1)
        self._frame_scale.config(from_=float(self._t0), to=float(self._t_max))
        t = min(max(self.app.cursor.t, self._t0), self._t_max)
        self._syncing_slider = True
        self._frame_var.set(float(t))
        self._syncing_slider = False
        self._frame_label.config(text=str(t))

    def _on_view_changed(self) -> None:
        self._apply_time_window()
        if self.settings.auto_resolution_on_zoom:
            self._resolution_var.set(float(self.app.position_plot.resolution))
        self._refresh_all()

    def _on_reset_zoom(self) -> None:
        self.app.reset_zoom()

    def _on_save_defaults(self) -> None:
        """Persist the current view state to settings.yaml as startup defaults."""
        self.settings = self.settings.model_copy(
            update={
                "default_preset": self._preset_var.get(),
                "default_playback_speed": _SPEED_BY_LABEL.get(self._speed_var.get(), 1.0),
                "default_team_focus": self._team_var.get(),
                "default_possession_filter": self._possession_keys.get(
                    self._possession_var.get(), "all"
                ),
                "default_ball_in_play": self._ball_in_play_var.get(),
                "default_home_at_bottom": self._home_bottom_var.get(),
                "default_resolution": int(self._resolution_var.get()),
            }
        )
        self.app.settings = self.settings
        try:
            save_settings(self.settings)
        except OSError as exc:
            self._set_settings_status(f"Save failed: {exc}")
        else:
            self._set_settings_status(f"Saved to {DEFAULT_SETTINGS_PATH.name} ✓")

    def _on_reset_defaults(self) -> None:
        """Restore built-in view defaults, apply them live, and persist them."""
        defaults = UserSettings()
        self.settings = self.settings.model_copy(
            update={
                "default_preset": defaults.default_preset,
                "default_playback_speed": defaults.default_playback_speed,
                "default_team_focus": defaults.default_team_focus,
                "default_possession_filter": defaults.default_possession_filter,
                "default_ball_in_play": defaults.default_ball_in_play,
                "default_home_at_bottom": defaults.default_home_at_bottom,
                "default_resolution": defaults.default_resolution,
            }
        )
        self.app.settings = self.settings
        self._apply_view_settings(self.settings)
        try:
            save_settings(self.settings)
        except OSError as exc:
            self._set_settings_status(f"Reset failed: {exc}")
        else:
            self._set_settings_status("Restored built-in defaults ✓")

    def _apply_view_settings(self, s: UserSettings) -> None:
        """Push the view-state settings onto the live widgets and controller."""
        if self._playing:
            self._stop_play()

        if s.default_preset in self._presets:
            self._preset_var.set(s.default_preset)
            self.preset = load_preset(self._presets[s.default_preset])
            self.app.on_preset_change(self.preset)
            self._rebuild_layer_toggles()

        self._speed_var.set(self._speed_label(s.default_playback_speed))
        self.app.timeline.on_speed_change(s.default_playback_speed)
        self._play_step = max(1, round(2 * s.default_playback_speed))

        self._team_var.set(s.default_team_focus)
        self.app.position_plot.set_team_focus(s.default_team_focus)

        self._possession_var.set(self._possession_label(s.default_possession_filter))
        self.app.position_plot.set_possession_filter(s.default_possession_filter)

        self._ball_in_play_var.set(s.default_ball_in_play)
        self.app.position_plot.set_ball_in_play(s.default_ball_in_play)

        self._home_bottom_var.set(s.default_home_at_bottom)
        self.app.set_home_at_bottom(s.default_home_at_bottom)

        self._resolution_var.set(float(s.default_resolution))
        self.app.set_resolution(s.default_resolution)

        self._refresh_all()

    def _open_settings_dialog(self) -> None:
        if self._settings_dialog is not None and self._settings_dialog.winfo_exists():
            self._settings_dialog.lift()
            self._settings_dialog.focus_set()
            return

        dialog = tk.Toplevel(self.root)
        self._settings_dialog = dialog
        dialog.title("Settings")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.protocol("WM_DELETE_WINDOW", self._close_settings_dialog)

        wrap = 380
        body = ttk.Frame(dialog, padding=18)
        body.pack(fill="both", expand=True)

        ttk.Label(
            body,
            text="Startup defaults",
            font=("TkDefaultFont", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            body,
            text="Preferences are stored in settings.yaml and loaded when the app starts.",
            wraplength=wrap,
            justify="left",
            foreground="#333333",
        ).pack(anchor="w", pady=(4, 14))

        ttk.Label(
            body, text="Save current view", font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w")
        ttk.Label(
            body,
            text=(
                "Stores the current preset, playback speed, team and possession "
                "filters, pitch orientation and heatmap resolution as the startup "
                "defaults."
            ),
            wraplength=wrap,
            justify="left",
        ).pack(anchor="w", pady=(2, 12))

        ttk.Label(
            body, text="Reset to defaults", font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w")
        ttk.Label(
            body,
            text="Puts those same options back to the built-in values.",
            wraplength=wrap,
            justify="left",
        ).pack(anchor="w", pady=(2, 12))

        ttk.Label(
            body,
            text=(
                "Other keys (match data folder, cache, analytics stride, zoom "
                "behaviour) are edited directly in the file:"
            ),
            wraplength=wrap,
            justify="left",
            foreground="#555555",
        ).pack(anchor="w")
        ttk.Label(
            body,
            text=str(DEFAULT_SETTINGS_PATH),
            wraplength=wrap,
            justify="left",
            foreground="#888888",
        ).pack(anchor="w", pady=(2, 0))

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=16)

        btns = ttk.Frame(body)
        btns.pack(fill="x")
        ttk.Button(
            btns, text="Save current view", width=18, command=self._on_save_defaults
        ).pack(side="left")
        ttk.Button(
            btns, text="Reset to defaults", width=18, command=self._on_reset_defaults
        ).pack(side="left", padx=(10, 0))
        ttk.Button(
            btns, text="Close", width=8, command=self._close_settings_dialog
        ).pack(side="right")

        self._settings_status = tk.StringVar(value="")
        ttk.Label(
            body, textvariable=self._settings_status, foreground="#1a7f37"
        ).pack(anchor="w", pady=(14, 0))

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + 60
        y = self.root.winfo_rooty() + 60
        dialog.geometry(f"+{x}+{y}")

    def _close_settings_dialog(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.destroy()
            self._settings_dialog = None
        self._settings_status = None

    def _set_settings_status(self, text: str) -> None:
        status = getattr(self, "_settings_status", None)
        if status is not None:
            status.set(text)

    # -------------------------------------------------------------- callbacks

    def _on_scrub(self, t: int) -> None:
        t = max(self._t0, min(int(t), self._t_max))
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

    def _on_period_choice(self, _choice: str) -> None:
        if self._playing:
            self._stop_play()
        period = self._period_keys.get(self._period_var.get())
        self.app.set_period(period)

    def _on_orientation_toggle(self) -> None:
        self._home_bottom_var.set(not self._home_bottom_var.get())
        self.app.set_home_at_bottom(self._home_bottom_var.get())
        self._refresh_all()

    def _on_ball_in_play(self) -> None:
        self.app.position_plot.set_ball_in_play(self._ball_in_play_var.get())
        self._refresh_all()

    def _on_possession_choice(self, _choice: str) -> None:
        value = self._possession_keys.get(self._possession_var.get(), "all")
        self.app.position_plot.set_possession_filter(value)
        self._refresh_all()

    def _on_resolution_drag(self, _value: str) -> None:
        # no-op during drag — full redraw is expensive on real matches
        return

    def _on_resolution_release(self, _event=None) -> None:
        self.app.set_resolution(int(self._resolution_var.get()))
        self._refresh_all()

    def _on_layer_toggle(self, name: str, var: tk.BooleanVar) -> None:
        self.app.toggle_layer(name, var.get())
        self._refresh_all()

    def _on_timeline_layer_toggle(self, name: str, var: tk.BooleanVar) -> None:
        self.app.toggle_timeline_layer(name, var.get())
        self._refresh_all()

    def _on_position_layer_toggle(self, name: str, var: tk.BooleanVar) -> None:
        self.app.toggle_position_layer(name, var.get())
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
            self._on_scrub(self._t0)
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
        if t > self._t_max:
            self._on_scrub(self._t_max)
            self._stop_play()
            return
        self._on_scrub(t)
        self._play_after_id = self.root.after(self.settings.play_interval_ms, self._play_tick)

    def _on_close(self) -> None:
        self._stop_play()
        for canvas in self._canvases:
            widget = canvas.get_tk_widget()
            widget.destroy()
        self.root.destroy()

    # ------------------------------------------------------------------- run

    def run(self) -> None:
        self.root.mainloop()
