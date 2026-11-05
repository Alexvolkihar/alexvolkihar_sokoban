import pytest

from alexvolkihar_sokoban.persistence.migrations import MigrationError, MigrationRegistry

FMT = "alexvolkihar-sokoban/test"


def _v1_to_v2(d: dict[str, object]) -> dict[str, object]:
    return {**d, "b": 2}


def _v2_to_v3(d: dict[str, object]) -> dict[str, object]:
    return {**d, "c": 3}


def test_upgrade_chains_steps_in_order() -> None:
    reg = MigrationRegistry()
    reg.register(FMT, 2, _v2_to_v3)
    reg.register(FMT, 1, _v1_to_v2)
    assert reg.upgrade(FMT, {"a": 1}, 1, 3) == {"a": 1, "b": 2, "c": 3}
    assert reg.upgrade(FMT, {"a": 1}, 2, 3) == {"a": 1, "c": 3}


def test_upgrade_same_version_is_identity_copy() -> None:
    data: dict[str, object] = {"a": 1}
    out = MigrationRegistry().upgrade(FMT, data, 1, 1)
    assert out == data and out is not data


def test_upgrade_does_not_mutate_input() -> None:
    reg = MigrationRegistry()

    def mutating(d: dict[str, object]) -> dict[str, object]:
        d["x"] = 1
        return d

    reg.register(FMT, 1, mutating)
    data: dict[str, object] = {"a": 1}
    assert reg.upgrade(FMT, data, 1, 2) == {"a": 1, "x": 1}
    assert data == {"a": 1}


def test_missing_step_raises() -> None:
    reg = MigrationRegistry()
    reg.register(FMT, 1, _v1_to_v2)
    with pytest.raises(MigrationError, match="2 -> 3"):
        reg.upgrade(FMT, {}, 1, 3)


def test_steps_are_per_format() -> None:
    reg = MigrationRegistry()
    reg.register(FMT, 1, _v1_to_v2)
    with pytest.raises(MigrationError):
        reg.upgrade("alexvolkihar-sokoban/other", {}, 1, 2)


def test_downgrade_raises() -> None:
    with pytest.raises(MigrationError):
        MigrationRegistry().upgrade(FMT, {}, 3, 1)


def test_duplicate_registration_raises() -> None:
    reg = MigrationRegistry()
    reg.register(FMT, 1, _v1_to_v2)
    with pytest.raises(ValueError):
        reg.register(FMT, 1, _v1_to_v2)


def test_invalid_from_version_raises() -> None:
    with pytest.raises(ValueError):
        MigrationRegistry().register(FMT, 0, _v1_to_v2)
