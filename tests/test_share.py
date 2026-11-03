from __future__ import annotations

from timeflow.models import AppUsage
from timeflow.share import OTHER_KEY, build_share_slices


def app(key: str, seconds: int, name: str | None = None) -> AppUsage:
    return AppUsage(key=key, name=name or key.title(), exe_path="", seconds=seconds)


def test_empty_input_yields_no_slices() -> None:
    assert build_share_slices([]) == []


def test_zero_second_apps_are_ignored() -> None:
    slices = build_share_slices([app("a", 0), app("b", 10)])
    assert [s.key for s in slices] == ["b"]


def test_fewer_apps_than_limit_keeps_every_one() -> None:
    slices = build_share_slices([app("a", 30), app("b", 90), app("c", 60)], limit=5)
    assert [(s.key, s.seconds) for s in slices] == [("b", 90), ("c", 60), ("a", 30)]
    assert all(not s.is_other for s in slices)


def test_more_apps_than_limit_folds_the_tail() -> None:
    apps = [app(f"app{i}", 100 - i) for i in range(8)]
    slices = build_share_slices(apps, limit=5)

    assert len(slices) == 5
    assert [s.key for s in slices[:4]] == ["app0", "app1", "app2", "app3"]
    other = slices[-1]
    assert other.key == OTHER_KEY
    assert other.is_other
    assert other.apps == 4
    assert other.name == "其他 4 个应用"
    assert other.seconds == sum(a.seconds for a in apps[4:])
    assert sum(s.seconds for s in slices) == sum(a.seconds for a in apps)


def test_limit_of_one_collapses_everything() -> None:
    slices = build_share_slices([app("a", 5), app("b", 7)], limit=1)
    assert len(slices) == 1
    assert slices[0].is_other
    assert slices[0].apps == 2
    assert slices[0].seconds == 12


def test_exactly_limit_apps_get_no_other_slice() -> None:
    apps = [app(f"app{i}", 10 + i) for i in range(5)]
    slices = build_share_slices(apps, limit=5)
    assert len(slices) == 5
    assert not any(s.is_other for s in slices)


def test_ties_are_broken_by_name() -> None:
    slices = build_share_slices([app("b", 10, "Beta"), app("a", 10, "Alpha")])
    assert [s.name for s in slices] == ["Alpha", "Beta"]
