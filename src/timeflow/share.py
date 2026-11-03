"""Share-of-time maths for the dashboard pie chart.

Kept free of Qt so the folding rule (top apps + one "其他" wedge) can be
unit-tested without a widget toolkit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import AppUsage

OTHER_KEY = "__other__"


@dataclass(frozen=True)
class ShareSlice:
    """One wedge of the app-share pie."""

    key: str
    name: str
    seconds: int
    apps: int = 1

    @property
    def is_other(self) -> bool:
        return self.key == OTHER_KEY


def build_share_slices(apps: Sequence[AppUsage], limit: int = 5) -> list[ShareSlice]:
    """Return at most ``limit`` wedges, biggest first.

    The first ``limit - 1`` apps keep their own wedge; everything else is
    folded into a single "其他 N 个应用" wedge so the chart stays readable.
    Apps without recorded seconds are dropped, so an empty range yields an
    empty list.
    """
    limit = max(1, int(limit))
    ranked = sorted(
        (app for app in apps if app.seconds > 0),
        key=lambda app: (-app.seconds, app.name.lower()),
    )
    if len(ranked) <= limit:
        return [ShareSlice(app.key, app.name, int(app.seconds)) for app in ranked]

    slices = [
        ShareSlice(app.key, app.name, int(app.seconds)) for app in ranked[: limit - 1]
    ]
    rest = ranked[limit - 1 :]
    slices.append(
        ShareSlice(
            OTHER_KEY,
            f"其他 {len(rest)} 个应用",
            sum(int(app.seconds) for app in rest),
            len(rest),
        )
    )
    return slices
