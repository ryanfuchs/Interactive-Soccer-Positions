"""DFL match sections — keys, display order, and UI labels."""
from __future__ import annotations

# Ordered map: floodlight / DFL section id → UI label
SECTION_LABELS: dict[str, str] = {
    "firstHalf": "1st Half",
    "secondHalf": "2nd Half",
    "firstHalfExtra": "ET 1st",
    "secondHalfExtra": "ET 2nd",
    "penaltyShootout": "Penalties",
}

SECTION_ORDER: tuple[str, ...] = tuple(SECTION_LABELS)


def section_display_name(section: str) -> str:
    if section in SECTION_LABELS:
        return SECTION_LABELS[section]
    spaced = section.replace("_", " ")
    out = []
    for i, ch in enumerate(spaced):
        if i and ch.isupper() and not spaced[i - 1].isspace():
            out.append(" ")
        out.append(ch)
    return "".join(out).strip().title() or section
