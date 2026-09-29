import pytest

from apps.geo.gazetteer import normalize_place


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("St. Louis", "saint louis"),
        ("Saint Louis", "saint louis"),
        ("Ft. Wayne", "fort wayne"),
        ("Fort Wayne", "fort wayne"),
        ("Mt. Vernon", "mount vernon"),
        ("Mount Vernon", "mount vernon"),
        ("O'Fallon", "ofallon"),
        ("Winston-Salem", "winston salem"),
        ("McAlester", "mcalester"),
        ("New York, NY", "new york ny"),
        ("Salt Lake City", "salt lake city"),
        ("Coeur d'Alene", "coeur dalene"),
        ("Fond du Lac", "fond du lac"),
        ("Port St. Lucie", "port saint lucie"),
        ("St. Petersburg", "saint petersburg"),
        ("Ft. Lauderdale", "fort lauderdale"),
        ("Mt. Pleasant", "mount pleasant"),
        ("Lee's Summit", "lees summit"),
        ("Boise City", "boise city"),
        ("El Paso", "el paso"),
        ("Baton Rouge", "baton rouge"),
        ("Grand Rapids & North", "grand rapids and north"),
        ("Hot Springs National Park", "hot springs national park"),
        ("La Crosse", "la crosse"),
        ("Des Moines", "des moines"),
        ("Corpus Christi", "corpus christi"),
        ("San José", "san jose"),
    ],
)
def test_normalize_place_user_side(raw, expected):
    assert normalize_place(raw, is_census=False) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("St. Louis city", "saint louis"),
        ("Springfield town", "springfield"),
        ("Hempstead village", "hempstead"),
        ("State College borough", "state college"),
        ("Amherst CDP", "amherst"),
        ("Princeton municipality", "princeton"),
        ("Upper Darby township", "upper darby"),
        ("Clinton charter township", "clinton"),
        ("Township of Clinton", "clinton"),
        ("Charter Township of Clinton", "clinton"),
    ],
)
def test_normalize_place_census_side(raw, expected):
    assert normalize_place(raw, is_census=True) == expected
