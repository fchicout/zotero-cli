"""
Keeps untrusted text (item titles, URLs, notes, collection and tag names,
third-party API data) from controlling the user's terminal.

Anyone who can edit a shared group library, and any metadata source, can
put escape sequences in that text. Printed raw, an OSC 52 sequence writes
the user's clipboard and an OSC 8 sequence disguises a link. Rich's `Text`
keeps them, so every console in the app is a `SafeConsole`, which strips
control characters from the text it renders while keeping Rich's own
styling. Text interpolated into Rich markup also needs `safe_markup`, so a
title like "[link=...]" or "[/bold]" is shown literally instead of being
parsed as markup.
"""

import re
from typing import Any, Iterable, Optional

from rich.console import Console, ConsoleOptions, RenderableType
from rich.markup import escape
from rich.segment import Segment

# C0 controls except tab and newline (ESC, BEL, CR, ...), DEL, C1 controls
# (including the 8-bit CSI/OSC introducers), and the Unicode bidi
# overrides/isolates that can make text display in a different order than
# it reads.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def strip_controls(text: str) -> str:
    """Removes terminal control characters from `text`, keeping tabs and
    newlines."""
    return _CONTROL_RE.sub("", text)


def safe_markup(value: Any) -> str:
    """`value` as a string that is safe to interpolate into Rich markup:
    control characters removed and markup escaped."""
    return escape(strip_controls("" if value is None else str(value)))


class SafeConsole(Console):
    """A Rich Console that strips control characters from rendered text.
    Rich's own styling and cursor control are separate segments, so colours
    and layout are unaffected."""

    def render(
        self, renderable: RenderableType, options: Optional[ConsoleOptions] = None
    ) -> Iterable[Segment]:
        for segment in super().render(renderable, options):
            if segment.control is None and segment.text:
                cleaned = strip_controls(segment.text)
                if cleaned != segment.text:
                    segment = Segment(cleaned, segment.style, segment.control)
            yield segment
