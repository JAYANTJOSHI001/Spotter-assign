import io
from decimal import Decimal

import pandas as pd

from apps.stations.pipeline import prepare_stations_dataframe


def test_prepare_stations_on_synthetic_data():
    csv_data = """OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
1001,Pilot Travel Center,123 Main St,Springfield ,IL,50,3.459
1001,Pilot #1001,123 Main St,Springfield,IL,50,3.359
1001,Pilot Travel Center,123 Main St,Springfield ,IL,50,3.459
1002,Flying J #200,456 Highway Rd,Fort Wayne  ,IN,51,3.299
1002,Flying J #200,456 Highway Rd,Fort Wayne,IN,51,3.299
1003,Love's Travel Stop,789 Interstate,Calgary,AB,99,4.199
1004,Petro Stopping Center,321 Truck Way,Toronto,ON,98,4.599
1005,TA Express,555 Country Rd,Vancouver,BC,97,4.899
1006,Roady's Truck Stop,10 Route 66,Dallas,TX,60,3.159
1006,Roady's Truck Stop,10 Route 66,Dallas,TX,60,3.259
1006,Roady's,10 Route 66,Dallas,TX,60,3.059
1007,Cheap Stop,11 Outlaw Rd,Denver,CO,70,0.999
1008,Super Expensive,12 Luxury Blvd,Miami,FL,80,12.500
1009,Shell Truck Stop,100 Interstate 80,Des Moines,IA,40,3.399
1010,BP Travel Plaza,200 US-30,Cedar Rapids,IA,41,3.419
1011,Casey's General Store,300 Highway 6,Iowa City,IA,42,3.389
1012,Kum & Go,400 Interstate 35,Ames,IA,43,3.379
1013,Kwik Trip,500 State Hwy 9,Decorah,IA,44,3.359
1014,Sinclair Dino Mart,600 US-71,Spencer,IA,45,3.369
1015,Speedway #1015,700 I-29,Sioux City,IA,46,3.349
1016,Exxon Tiger Mart,800 US-34,Burlington,IA,47,3.429
1017,Chevron Station,900 US-63,Ottumwa,IA,48,3.439
1018,Mobil Mart,1010 US-20,Dubuque,IA,49,3.449
1019,Phillips 66,1111 US-18,Mason City,IA,52,3.459
1020,Valero Express,1212 US-65,Marshalltown,IA,53,3.469
1021,Sunoco Travel Plaza,1313 US-169,Fort Dodge,IA,54,3.479
1022,Marathon Station,1414 US-75,Le Mars,IA,55,3.489
1023,Citgo Mart,1515 US-6,Newton,IA,56,3.499
1024,Conoco Stop,1616 US-30,Clinton,IA,57,3.509
1025,Texaco Plaza,1717 US-61,Keokuk,IA,58,3.519
"""
    raw_df = pd.read_csv(io.StringIO(csv_data), dtype=str)
    assert len(raw_df) == 30

    clean_df, stats = prepare_stations_dataframe(raw_df, policy="min", assert_audit=False)

    # 3 Canadian rows dropped: 1003 (AB), 1004 (ON), 1005 (BC)
    assert stats["canadian_rows_dropped"] == 3

    # Exact duplicates dropped: row 3 is dup of row 1, row 5 is dup of row 4
    assert stats["exact_duplicates_dropped"] == 2

    # Out of range prices excluded: 1007 (0.999 < 1.5), 1008 (12.500 > 10.0)
    assert stats["excluded_price_rows"] == 2

    # Check station 1001:
    # 2 remaining rows with prices 3.459 and 3.359 -> min policy selects 3.359
    # Names: "Pilot Travel Center" (len 19) vs "Pilot #1001" (len 10) -> longest name selected
    st_1001 = clean_df[clean_df["opis_id"] == 1001].iloc[0]
    assert st_1001["price"] == Decimal("3.359")
    assert st_1001["price_min"] == Decimal("3.359")
    assert st_1001["price_max"] == Decimal("3.459")
    assert st_1001["n_price_rows"] == 2
    assert st_1001["name"] == "Pilot Travel Center"
    assert st_1001["city"] == "Springfield"  # trailing space stripped

    # Check station 1002:
    st_1002 = clean_df[clean_df["opis_id"] == 1002].iloc[0]
    assert st_1002["city"] == "Fort Wayne"

    # Check station 1006:
    st_1006 = clean_df[clean_df["opis_id"] == 1006].iloc[0]
    assert st_1006["price"] == Decimal("3.059")
    assert st_1006["name"] == "Roady's Truck Stop"  # longer than "Roady's"
