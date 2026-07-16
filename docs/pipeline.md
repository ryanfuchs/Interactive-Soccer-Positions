# SoPoVis — from raw data to pixels

This document walks the full path a match takes through the system: DFL XML
files → `MatchState` → analytics → `PrecomputedBundle` → config-driven
rendering → the three coordinated views. Each stage ends with the design
questions you are most likely to be asked about it, and the scientific
reasoning behind the answers.

```
DFL XML triplet                     (02_01 metadata, 03_02 events, 04_03 tracking)
      │  io/ingest.py
      ▼
MatchState                          (T, N, 5) arrays + events + metadata
      │  bundle/builder.py          registered producers → named products (strided)
      ▼
PrecomputedBundle                   products map, O(1) per-frame lookups, disk-cached
      │  render/*                   YAML preset → element stacks
      ▼
SceneRenderer / TimelineStack       pitch layers / timeline layers
      │  ui/*                       FrameCursor pub-sub
      ▼
Timeline · Position plot · Pitch    three coordinated matplotlib views in Tk
```

---

## 1. Ingestion (`sopovis/io`)

A match arrives as a *triplet* of DFL Bundesliga XML files, discovered and
grouped by `MatchId` (`io/files.py`):

| Feed | Content | Loader |
|---|---|---|
| `02_01` matchinformation | teams, players, shirt colors, pitch size | `MetadataLoader` — direct DOM parse |
| `03_02` events_raw | shots, cards, subs, whistles, … | `EventLoader` — via floodlight |
| `04_03` positions_raw_observed | 25 fps player + ball positions | `TrackingDataLoader` — via floodlight |

**Metadata** (`io/metadata.py`). The file is ~12 KB, so a full
`ElementTree` parse is fine. We bypass floodlight here because its teamsheet
reader drops team shirt colors and match-level info (result, stadium, pitch
dimensions) that the UI needs.

**Tracking** (`io/tracking.py`). floodlight's `read_position_data_xml`
returns per-section, per-team XY objects in *center-origin* metres. The
loader:

1. stacks home + away players into one `(T, N, 2)` array (home columns
   first, ordered by floodlight's `xID`),
2. concatenates the game sections (`firstHalf`, `secondHalf`, extra time,
   …) along the time axis, recording `section_ranges` as
   `(start, end_exclusive)` frame intervals,
3. shifts coordinates to *corner-origin*: `x ∈ [0, pitch_x]`,
   `y ∈ [0, pitch_y]`, `(0, 0)` bottom-left,
4. derives speed, acceleration and cumulative distance numerically from
   position deltas (floodlight discards the S/A/D attributes present in the
   raw feed). Kinematics are computed **per section** so the half-time
   teleport doesn't create an artificial 10 km/h spike,
5. keeps `NaN` where a player is absent (bench, substituted off) — absence
   is data, not an error.

The result is `frames: (T, N, 5)` = x, y, speed, accel, distance, plus
`ball: (T, 4)` = x, y, z, in-play status, and `ball_possession: (T,)`
(1 home / 2 away / 0 contested).

**Events** (`io/events.py`). floodlight gives per-section event dataframes
with a `gameclock` in seconds from section start. Alignment to tracking:
`frame_idx = section_start + round(gameclock · frame_rate)`, clamped into
the section. Every event becomes an immutable `EventMoment` with the raw
qualifier dict preserved for tooltips.

**`MatchState`** (`model/state.py`) is the single time-indexed store that
everything downstream reads: arrays, `player_registry`, `event_index`
(frame → events), `section_ranges`, metadata. The coordinate convention is
fixed here once — all analytics and rendering assume corner-origin metres.

### Questions you may be asked

- *Why one `(T, N, 5)` array instead of per-player objects?*
  Contiguous NumPy arrays give O(1) frame slicing (`frames[t]`) and let
  analytics vectorize over players; an object-per-player model would force
  Python-level loops at 25 fps × ~140k frames. This is the
  structure-of-arrays vs. array-of-structures argument: the access pattern
  is "all players at time t", so time must be the leading axis.
- *Why concatenate sections instead of keeping them separate?*
  A single global frame index makes the cursor, the timeline and zooming
  trivial (one integer). Section semantics are recoverable through
  `section_ranges`, and everything that needs section awareness (clock
  labels, kinematics, attack directions) consults it explicitly.
- *Why corner-origin coordinates?*
  Rendering (mplsoccer's `VerticalPitch`) and role inference both want
  non-negative pitch coordinates; converting once at the boundary is safer
  than remembering the convention at every use site (a classic
  parse-don't-validate argument).
- *Why derive kinematics numerically rather than trusting the feed?*
  floodlight discards the feed's S/A/D attributes, so they are simply not
  available post-parse; deriving them from positions keeps a single source
  of truth and works for any provider.
- *How accurate is the event-to-frame alignment?*
  ±0.5 s by construction (the game clock has 1 s resolution ≈ 25 frames).
  Sufficient for timeline markers; not sufficient for e.g. automatic pass
  detection, which would need the tracking itself.

---

## 2. Analytics (`sopovis/analytics`, `sopovis/bundle`)

Analytics run once per match, over a **strided subsample** of frames
("analytics frames", default stride 5 → 5 Hz). Each analytic is a
**producer** (`analytics/producers.py`) registered by name, mirroring the
element registry on the render side: a producer declares its `name`,
`version`, dependencies (`requires`) and tunables (`params`), and turns the
`MatchState` into one named **product**. `BundleBuilder` computes the core
products (`attack_directions`, `shape_graph`, `roles`) eagerly; any other
registered product (e.g. `proximity`) is computed on first
`bundle.product(name)` access — enabling a layer triggers exactly the
analytics it needs, once. The built-in producers:

### 2.1 Shape graphs (`shape_graph.py`)

Per team per analytics frame, on the ten outfield players:

1. **Delaunay triangulation** of the positions.
2. **Iterative edge reduction**: repeatedly remove the edge whose combined
   apex angles (the angles subtended by the edge at its adjacent triangle
   apexes) exceed 135° (π·¾), with a priority heap ordering removals.

The result is a planar graph that captures *tactical adjacency* — who is
directly beside/behind whom — while dropping the long "shortcut" edges of
the raw triangulation (e.g. left back ↔ right winger). Degenerate frames
(coincident points, < 3 players, Qhull failures) fall back to trivial
graphs.

Edges are stored compactly as `(E, 2)` arrays of player-column pairs per
frame; a `networkx.Graph` is materialised only on demand.

### 2.2 Tactical roles (`roles.py`)

Roles are discrete cells on a **5×5 grid**: depth
`x_role ∈ {−2 … +2}` (Forward → Back) and lateral `y_role ∈ {−2 … +2}`
(Left → Right), i.e. "LCM", "RB", … via `ROLE_NAMES`.

Assignment (`frame_to_position_plot`) splits the team recursively:

1. Build the shape graph of the current subset.
2. Find its internal faces and their **barycenters**.
3. Split the players into left-of / right-of (or in front-of / behind) the
   barycenter band; players inside the band stay at 0.
4. Recurse twice per axis → values in `[−2, 2]`.

The split is *relative to team shape*, not absolute pitch position: a high
defensive line's center backs are still "Back". `attacking_positive_x`
flips both axes so "Forward" always means toward the opponent goal; the
direction itself is inferred per team per section from the goalkeeper's
mean position in the first ~100 s (`infer_attack_directions`).

### 2.3 Temporal aggregation (`pipeline.py`)

- `role_counts (Ta, N, 25)`: **cumulative** histogram of role cells per
  player. Any time window `[a, b]` reduces to `counts[b] − counts[a]` —
  O(1) per query, which is what makes interactive re-binning of the
  position plot cheap (a prefix-sum / summed-area-table idea).
- **Substitutions** are detected as changes in the set of present players
  between consecutive analytics frames.
- **Row order** for the position plot: starters are ordered row-major on
  the 5×5 grid (depth first, then lateral, shirt number as tiebreak);
  each incoming substitute inherits the row of the most role-similar
  outgoing player (greedy minimum assignment on squared grid distance), so
  rows stay stable and comparable across the match.

### 2.4 Bundle + cache (`bundle/`)

Everything lands in `PrecomputedBundle`: pass-through arrays plus a
`products` map (name → producer output) in which every render-time query
is O(1) (`positions(t)`, `roles_at(t)`, `edges_at(t, relation, team)`,
`clock_label(t)`). A `ProductSupplier` attached to the bundle computes
missing products on first access, resolving producer dependencies
recursively. The cache (`ProductCache`) writes **one pickle per product**
(`.cache/{match}.{product}.pkl`), each keyed by source hash, stride and
the producer's version + params — so adding or re-versioning one analytic
never invalidates the others. Pass-through arrays are never cached; they
are rebuilt from `MatchState` (~100 MB cached instead of ~400 MB).

### Questions you may be asked

- *How do I add a new analytic (pitch control, passing options, …)?*
  Subclass `Producer` (name, version, optional `requires`/`params`),
  implement `compute()`, register it in `default_producer_registry()`.
  Nothing else changes: the bundle, cache and views are generic over
  products. `ProximityEdgesProducer` exists as a worked example — plus one
  preset line it becomes a pitch overlay with zero render-code changes.
- *Why precompute instead of computing on scrub?*
  The UI contract is "any frame in O(1)". Shape graphs take milliseconds
  per frame — fine once, but not at 25 fps scrubbing, and the role model
  needs *whole-match* aggregation (row ordering, histograms) anyway, which
  cannot be computed incrementally while scrubbing forward.
- *Why stride 5?*
  Tactical structure changes on the order of seconds, not 40 ms; 5 Hz
  keeps the analytics pass and cache ~5× cheaper with no visible loss —
  the same argument as Nyquist sampling: the signal of interest
  (formation) is far below 2.5 Hz.
- *Why Delaunay + angle reduction instead of k-nearest-neighbours or a
  distance threshold?*
  Delaunay is parameter-free, scale-invariant and planar; kNN needs a k
  that fits both a compact back line and a stretched counter-attack, and
  distance thresholds break the moment the team block compresses. The
  135° reduction removes exactly the edges that connect players who have
  other players "between" them in the angular sense — a perceptually
  motivated adjacency criterion.
- *Why relative (shape-based) roles instead of absolute pitch zones?*
  Absolute zones conflate formation with field position: during a deep
  defensive phase every player would be "Back". Splitting on the team's
  own barycenters measures *structure*, which is what a tactical analyst
  means by "role", and matches how formations are defined (relative
  order, not coordinates).
- *Why a cumulative histogram rather than storing the role per bin?*
  The UI lets the user re-bin arbitrarily (resolution slider, zoom).
  Cumulative counts answer "dominant role in [a, b]" for any a, b in
  O(1) without recomputing — the prefix-sum trick.
- *How do you validate the inferred attack direction?*
  The goalkeeper is a near-invariant anchor: he stays in his own half
  essentially always, so his mean x over the first 100 s of a section
  identifies the defended goal with very high reliability; a whole-team
  fallback covers missing GK tracking.
- *Limitations?*
  Roles are undefined for < 2 tracked outfield players; the shape split is
  ambiguous for perfectly collinear formations (handled by a special
  case); event alignment is ±0.5 s; possession codes come from the
  provider and are not re-inferred.

---

## 3. Rendering (`sopovis/render`)

Rendering is **config-driven**: a preset YAML (`presets/*.yaml`) declares
two layer stacks — `layers:` for the pitch and `timeline:` for the event
strip. Both sides follow the *same* architecture:

| | Pitch | Timeline |
|---|---|---|
| Element base | `Element` (`Static` / `Dynamic`) | `TimelineElement` |
| Plug-in registry | `ElementRegistry` | `TimelineElementRegistry` |
| Builder (spec → stack) | `SceneBuilder` | `TimelineStackBuilder` |
| Draw loop owner | `SceneRenderer` | `TimelineStack` |
| Consumer view | `PitchAnimationView` | `TimelineControlView` |

An element is described by `LayerSpec` (name, type, z-order, enabled,
style dict). The registry maps `type` to a `from_spec` factory; adding an
overlay means: implement the element, register it, add a YAML entry. No
view code changes.

Relation *data* and relation *rendering* are separate concerns:
`EdgeSetOverlay` draws any edge-valued product named by its `relation`
style key (`shape_graph`, `proximity`, later passing options), so a new
relation is pure analytics and an alternative representation of an
existing relation is pure config.

- **Pitch elements** split into `StaticElement` (built once — pitch
  markings, half-space lines) and `DynamicElement` (update artist data in
  place per frame — player glyphs, ball, shape graph, defensive line,
  velocity arrows). In-place artist updates instead of re-creation are
  what keep scrubbing smooth.
- **Timeline elements** (possession chart, lane furniture, section
  boundaries, shot/card/sub/whistle markers) are rebuilt when the strip
  redraws (period change, zoom, layer toggle) — the strip is not animated
  per-frame, only its playhead line moves. Vertical placement uses named
  *bands* (`full` / `home` / `away`) from `TimelineGeometry`; each element
  also exposes `hover_targets()` for unified tooltip hit-testing.
- `meta.z_order` is forwarded to matplotlib artist zorder, so stacking is
  controlled by config, not draw-call order.

### Questions you may be asked

- *Why a registry + YAML instead of hardcoded draw functions?*
  Open/closed principle: visual experiments (new overlay, different
  theme) become data changes, and presets ("tactical" vs "broadcast")
  are just different layer stacks over identical code paths. It also
  makes layers individually toggleable and testable.
- *Why do pitch and timeline mirror each other's structure?*
  Once two subsystems solve the same problem (ordered, toggleable,
  config-declared layers), diverging structures double the learning and
  maintenance cost. The symmetry means a contributor who has added a pitch
  overlay already knows how to add a timeline overlay.
- *Why are timeline layers rebuilt while pitch layers update in place?*
  Different refresh rates: the pitch redraws at scrub rate (up to 25 Hz),
  so artist mutation matters; the timeline redraws only on discrete state
  changes, where rebuild cost is irrelevant and rebuild code is simpler.

---

## 4. UI (`sopovis/ui`)

Three coordinated matplotlib figures embedded in a Tk shell
(`MatchDesktopApp`), wired by `AppController`:

```
scrub / click / play ──► TimelineControlView.on_scrub ──► FrameCursor.set
                                                            │ (pub-sub)
                                    ┌───────────────────────┴───────┐
                                    ▼                               ▼
                     PositionPlotView.on_cursor_change   PitchAnimationView.on_cursor_change
```

- **`FrameCursor`** — single writer (the timeline), many read-only
  subscribers. The position plot never sets the cursor; its clicks
  *request* a seek through the timeline. One authority prevents feedback
  loops between views.
- **`ViewTimeRange`** — shared visible window = period filter ∩ zoom span.
  Drag-zoom on the timeline or position plot goes through
  `AppController.set_zoom`, which optionally adapts the heatmap resolution
  (`auto_resolution`) so the visible window always has ~`zoom_target_bins`
  bins.
- **`HoverLink`** — hovering a player in one view highlights him in the
  others and shows a tooltip.
- **Views** hold no data logic: they read the bundle and delegate drawing
  to `SceneRenderer` / `TimelineStack`.

### Control placement

Every control sits in the header of the view it affects:

| Location | Controls | Effect scope |
|---|---|---|
| App bar (top) | Preset, Period, Reset zoom | all views |
| Timeline header | Play, scrub slider, speed, Layers ▾ | timeline / playback |
| Position-plot header | Teams, In play, Possession, Resolution | heatmap only |
| Pitch header | Layers ▾, orientation swap | pitch only |

Layer toggles live in per-view **Layers ▾** dropdown menus instead of a
row of checkboxes: the set of layers is preset-dependent and unbounded,
menus scale where checkbox rows overflow, and showing seven rarely-used
toggles permanently taxes visual search on every glance (Hick's law).

Why controls belong next to what they control: by the Gestalt **law of
proximity**, spatial closeness is read as functional grouping, so
placement itself documents each control's scope where a global toolbar
would need labels; **Fitts's law** — pointing time grows with distance,
and eye travel between a control and the view it changes is feedback
distance too; and Norman's **mapping** principle - controls arranged like
their effects need no explanation. Practically, placement also answers
"which view will this change?" before the user clicks, which is what
makes the old single toolbar (a period dropdown beside a possession
filter beside pitch toggles) confusing despite containing the same
widgets.

### Questions you may be asked

- *Why is only the timeline allowed to write the cursor?*
  Multiple writers with mutual subscriptions create update cycles and
  race-y "who wins" semantics. Funneling all seeks through one owner is
  the standard unidirectional-data-flow argument (same reasoning as
  Flux/Elm architectures).
- *Why matplotlib in Tk rather than a game/graphics framework?*
  The views are quantitative plots (heatmap, event strip, metric pitch)
  needing axes, colormaps and data-space picking; matplotlib gives those
  for free, and blit-style artist updates make 25 fps feasible. Tk ships
  with CPython — zero extra runtime dependencies.
- *Why does zooming change the heatmap resolution?*
  Constant bin *count* rather than bin *width* keeps the visual
  information density constant: full-match view aggregates (~30 s bins),
  zoomed view resolves (~sub-second bins). This mirrors level-of-detail
  techniques in map rendering.

---

## 5. End-to-end trace of one user action

"User drags the speed dropdown to 4× and presses Play":

1. `MatchDesktopApp._on_speed_choice` sets `play_step = 8` frames per
   80 ms tick.
2. Each tick calls `_on_scrub(t + 8)` → `TimelineControlView.on_scrub`
   clamps to the visible window and calls `FrameCursor.set(t)`.
3. `FrameCursor` notifies subscribers:
   `PositionPlotView.on_cursor_change` moves its playhead line;
   `PitchAnimationView.on_cursor_change` calls `SceneRenderer.draw(ax,
   bundle, t)`, and each enabled `DynamicElement` reads
   `bundle.positions(t)` / `bundle.shape_edges_at(t, team)` — all O(1) —
   and mutates its artists.
4. The timeline updates its own playhead and clock label; canvases redraw.

No stage recomputes analytics; playback is pure lookup.
