from apps.geo.bounds import in_supported_us


def test_us_border_cities_accepted():
    cities = {
        "Detroit, MI": (42.3314, -83.0458),
        "Buffalo, NY": (42.8864, -78.8784),
        "Seattle, WA": (47.6062, -122.3321),
        "El Paso, TX": (31.7619, -106.4850),
        "San Diego, CA": (32.7157, -117.1611),
        "Miami, FL": (25.7617, -80.1918),
        "Key West, FL": (24.5551, -81.7800),
        "Chicago, IL": (41.8781, -87.6298),
        "Dallas, TX": (32.7767, -96.7970),
        "New York, NY": (40.7128, -74.0060),
    }

    for name, (lat, lng) in cities.items():
        assert in_supported_us(lat, lng), f"Expected US border city '{name}' to be accepted"


def test_foreign_and_outside_locations_rejected():
    foreign = {
        "Toronto, Canada": (43.6532, -79.3832),
        "Vancouver, Canada": (49.2827, -123.1207),
        "Montreal, Canada": (45.5017, -73.5673),
        "Ottawa, Canada": (45.4215, -75.6972),
        "Calgary, Canada": (51.0447, -114.0719),
        "Tijuana, Mexico": (32.5149, -117.0382),
        "Juarez, Mexico": (31.7420, -106.4870),
        "Monterrey, Mexico": (25.6866, -100.3161),
        "Honolulu, HI (Outside contiguous US)": (21.3069, -157.8583),
        "Anchorage, AK (Outside contiguous US)": (61.2181, -149.9003),
        "London, UK": (51.5074, -0.1278),
    }

    for name, (lat, lng) in foreign.items():
        assert not in_supported_us(lat, lng), (
            f"Expected foreign/outside point '{name}' to be rejected"
        )
