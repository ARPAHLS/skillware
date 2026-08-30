"""Shared presentation themes for Skillware CLI modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from skillware.core.config import load_merged_config


@dataclass(frozen=True)
class ThemePalette:
    """Semantic Rich styles for one built-in CLI theme."""

    heading_style: str
    category_style: str
    id_style: str
    border_style: str
    splash_style: str
    menu_style: str
    error_color: str
    gradient_start: Tuple[int, int, int]
    gradient_mid: Tuple[int, int, int]
    gradient_end: Tuple[int, int, int]


THEMES: Dict[str, ThemePalette] = {
    "pastel": ThemePalette(
        heading_style="bold #C7CEEA",
        category_style="bold #FFDAC1",
        id_style="#B5EAD7",
        border_style="#C7CEEA",
        splash_style="#C7CEEA",
        menu_style="#FFDAC1",
        error_color="#FF9AA2",
        gradient_start=(0xD4, 0xE4, 0xF1),
        gradient_mid=(0x79, 0xB6, 0xD8),
        gradient_end=(0xEB, 0xD8, 0xDC),
    ),
    "ocean": ThemePalette(
        heading_style="bold #7DD3FC",
        category_style="bold #38BDF8",
        id_style="#BAE6FD",
        border_style="#0284C7",
        splash_style="#38BDF8",
        menu_style="#7DD3FC",
        error_color="#F87171",
        gradient_start=(0x0C, 0x4A, 0x6E),
        gradient_mid=(0x02, 0x84, 0xC7),
        gradient_end=(0x7D, 0xD3, 0xFC),
    ),
    "mono": ThemePalette(
        heading_style="bold #D0D0D0",
        category_style="bold #A8A8A8",
        id_style="#E0E0E0",
        border_style="#808080",
        splash_style="#C0C0C0",
        menu_style="#A8A8A8",
        error_color="#B0B0B0",
        gradient_start=(0xF0, 0xF0, 0xF0),
        gradient_mid=(0xA0, 0xA0, 0xA0),
        gradient_end=(0x60, 0x60, 0x60),
    ),
}


def active_theme() -> ThemePalette:
    """Return the configured palette; config normalization guarantees fallback."""
    theme_name = load_merged_config().presentation.theme
    return THEMES.get(theme_name, THEMES["pastel"])
