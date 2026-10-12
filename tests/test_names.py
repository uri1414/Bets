import pytest

from prop_engine.names import player_key


@pytest.mark.parametrize(
    "raw,key",
    [
        ("Marvin Harrison Jr.", "marvin harrison"),
        ("Marvin Harrison", "marvin harrison"),
        ("Ja'Marr Chase", "jamarr chase"),
        ("Amon-Ra St. Brown", "amon ra st brown"),
        ("D.K. Metcalf", "dk metcalf"),
        ("DK Metcalf", "dk metcalf"),
        ("Kenneth Walker III", "kenneth walker"),
        ("Rhamondre Stevenson", "rhamondre stevenson"),
    ],
)
def test_player_key(raw, key):
    assert player_key(raw) == key
