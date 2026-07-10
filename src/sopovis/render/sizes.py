"""Shared marker / glyph sizes used across the desktop UI.

Keep visual weight consistent between timeline icons, pitch players, and the ball.
Values are matplotlib point diameters unless noted.
"""

# Pitch glyphs (TeamColorGlyph / BallGlyph use diameter → scatter s = pt²)
PLAYER_MARKER_PT = 9.0
BALL_MARKER_PT = 5.5
SHIRT_FONT_SIZE = 6.5

# Hover ring around a selected player (matplotlib scatter ``s`` = area)
PLAYER_HIGHLIGHT_S = 260.0

# Timeline event markers (matplotlib ``markersize`` = diameter in points)
TIMELINE_MARKER_PT = 7.0
TIMELINE_INNER_DOT_PT = 2.5
TIMELINE_SCATTER_S = TIMELINE_MARKER_PT**2
