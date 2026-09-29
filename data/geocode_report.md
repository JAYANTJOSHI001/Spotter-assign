# FuelRoute Station Geocoding QA Report

## 1. Executive Summary
- **Total Clean Stations Input**: 6,626
- **Successfully Geocoded**: 6,611 (99.77%)
- **Excluded Stations**: 15 (0.23%)
- **Target Gate (≥ 98.00%)**: PASSED

## 2. Tier Breakdown
| Tier | Method | Confidence | Station Count | % of Clean Stations |
|---|---|---|---|---|
| 1 | Census Place Exact | 1.0 | 6,231 | 94.04% |
| 2 | Census County-Subdivision Exact | 1.0 | 110 | 1.66% |
| 3 | RapidFuzz Match (≥94) | ratio/100 | 13 | 0.20% |
| 4 | Nominatim Fallback | 0.8 | 257 | 3.88% |
| — | **Total Geocoded** | — | **6,611** | **99.77%** |

## 3. Tier 3 Fuzzy Matches
| State | Clean CSV City | Matched Census Place | Similarity Ratio |
|---|---|---|---|
| IN | grovertown | groverton | 94.7 |
| MI | middleton | middletown | 94.7 |
| NC | mc leansville | mcleansville | 96.0 |
| NV | mc dermitt | mcdermitt | 94.7 |
| NY | la fayette | lafayette | 94.7 |
| OH | brookpark | brook park | 94.7 |
| PA | mc kees rocks | mckees rocks | 96.0 |
| TN | mc donald | mcdonald | 94.1 |
| WI | de forest | deforest | 94.1 |
| WV | mineral wells | mineralwells | 96.0 |

## 4. Tier 4 Nominatim Matches
| City | State | Latitude | Longitude |
|---|---|---|---|
| Eastaboga | AL | 33.60594 | -86.02136 |
| Fackler | AL | 34.79258 | -85.90998 |
| Hope Hull | AL | 32.26986 | -86.35719 |
| Irvington | AL | 30.50686 | -88.23389 |
| Knoxville | AL | 33.59177 | -85.89719 |
| West Helena | AR | 34.54401 | -90.64262 |
| Dewey | AZ | 34.52976 | -112.24211 |
| Willow Beach | AZ | 35.86978 | -114.66007 |
| Canon City | CO | 38.44225 | -105.23488 |
| Dumont | CO | 39.76469 | -105.60034 |
| Milldale | CT | 41.56614 | -72.89997 |
| Baker | FL | 30.79723 | -86.68169 |
| Summerfield | FL | 29.00859 | -82.03481 |
| Youngstown | FL | 30.36436 | -85.43826 |
| Athens | GA | 33.95977 | -83.37640 |
| Augusta | GA | 33.47097 | -81.97484 |
| Cusseta | GA | 32.30543 | -84.77270 |
| Ellabell | GA | 32.12354 | -81.48567 |
| Ellenwood | GA | 33.61011 | -84.28798 |
| Fortson | GA | 33.37789 | -84.28881 |
| Macon | GA | 32.84069 | -83.63240 |
| Midland | GA | 32.57486 | -84.82715 |
| Rabun Gap | GA | 34.95721 | -83.38645 |
| Rising Fawn | GA | 34.76008 | -85.53108 |
| De Witt | IA | 41.82426 | -90.53813 |
| Boise | ID | 43.61662 | -116.20089 |
| Edwards | IL | 40.74587 | -89.74427 |
| La Salle | IL | 41.33337 | -89.09175 |
| Indianapolis | IN | 39.76833 | -86.15835 |
| Saint Croix | IN | 38.22395 | -86.58634 |
| Glendale | KY | 37.60173 | -85.90552 |
| Isom | KY | 37.18788 | -82.89877 |
| Lexington | KY | 38.04641 | -84.49704 |
| Middlesboro | KY | 36.60730 | -83.71433 |
| Pendleton | KY | 38.46229 | -85.30357 |
| Tollesboro | KY | 38.55952 | -83.57603 |
| Waddy | KY | 38.13702 | -85.07440 |
| Amite | LA | 30.72657 | -90.50898 |
| Bethany | LA | 32.37377 | -94.03796 |
| La Place | LA | 32.37847 | -85.86273 |
| Bridgewater | MA | 41.99022 | -70.97544 |
| Newton Lower Falls | MA | 42.32580 | -71.25634 |
| North Billerica | MA | 42.58526 | -71.28776 |
| North Oxford | MA | 42.15009 | -71.86841 |
| Curtis Bay | MD | 39.22522 | -76.59003 |
| Hunt Valley | MD | 39.49226 | -76.65895 |
| Millersville | MD | 39.05955 | -76.64802 |
| Newburg | MD | 38.37735 | -76.95331 |
| Nottingham | MD | 39.36400 | -76.45218 |
| Westover | MD | 38.12401 | -75.70632 |
| New Boston | MI | 42.16254 | -83.40299 |
| Newport | MI | 42.00227 | -83.30854 |
| Ottawa Lake | MI | 41.76415 | -83.74939 |
| Sault Sainte Marie | MI | 46.49767 | -84.34766 |
| Sawyer | MI | 41.88532 | -86.58947 |
| Smiths Creek | MI | 42.91392 | -82.60381 |
| Bois D Arc | MO | 37.25644 | -93.50770 |
| Ridgedale | MO | 36.50395 | -93.22379 |
| Sainte Genevieve | MO | 37.98144 | -90.04178 |
| Belden | MS | 34.31038 | -88.78839 |
| Lawrence | MS | 32.32514 | -89.23284 |
| Butte | MT | 46.01315 | -112.53651 |
| Milltown | MT | 46.87130 | -113.88172 |
| Candler | NC | 35.54444 | -82.68380 |
| Hamptonville | NC | 36.09847 | -80.76035 |
| Linwood | NC | 35.75069 | -80.31783 |
| Supply | NC | 34.01767 | -78.26750 |
| Winnabow | NC | 34.14934 | -78.09360 |
| Grassy Butte | ND | 47.39251 | -103.24797 |
| West Chesterfield | NH | 42.90425 | -72.51564 |
| Elizabethport | NJ | 40.65010 | -74.18709 |
| Monroe Township | NJ | 40.33576 | -74.43345 |
| Casa Blanca | NM | 35.04632 | -107.47139 |
| Clines Corners | NM | 35.00950 | -105.66918 |
| Tinnie | NM | 33.37056 | -105.22637 |
| Carson City | NV | 39.16633 | -119.76704 |
| Jean | NV | 35.77886 | -115.32438 |
| Moapa | NV | 36.66736 | -114.58498 |
| Castle Creek | NY | 42.22758 | -75.91825 |
| Gansevoort | NY | 43.19621 | -73.65140 |
| Glenmont | NY | 42.60480 | -73.76957 |
| Harpursville | NY | 42.17841 | -75.62463 |
| Hogansburg | NY | 44.97394 | -74.66324 |
| Irving | NY | 42.56756 | -79.11282 |
| New Hampton | NY | 41.40987 | -74.41174 |
| West Coxsackie | NY | 42.36064 | -73.81679 |
| Alvada | OH | 41.05033 | -83.40187 |
| Diamond | OH | 41.09895 | -81.02287 |
| North Jackson | OH | 41.10013 | -80.85717 |
| Pryor | OK | 36.30843 | -95.31691 |
| S Coffeyville | OK | 36.99452 | -95.62026 |
| Blakeslee | PA | 41.09251 | -75.59267 |
| Breezewood | PA | 39.99901 | -78.24042 |
| Brogue | PA | 39.87235 | -76.48464 |
| Drums | PA | 41.01814 | -75.99493 |
| Feasterville Trevose | PA | 40.14841 | -74.99347 |
| Greentown | PA | 41.32176 | -75.30546 |
| Lake Ariel | PA | 41.45397 | -75.38268 |
| Middlebury Center | PA | 41.84368 | -77.27442 |
| Monroeton | PA | 41.71258 | -76.47466 |
| Tafton | PA | 41.40453 | -75.18295 |
| Waterfall | PA | 40.12758 | -78.06278 |
| Batesburg | SC | 33.90792 | -81.54733 |
| Johns Island | SC | 32.69485 | -80.03425 |
| Leesville | SC | 33.91653 | -81.51344 |
| Longs | SC | 33.93853 | -78.73305 |
| Round O | SC | 32.93712 | -80.54094 |
| Townville | SC | 34.56371 | -82.89848 |
| Antioch | TN | 36.06006 | -86.67222 |
| Cedar Grove | TN | 36.25172 | -86.52777 |
| Denmark | TN | 35.53285 | -89.00395 |
| Hartford | TN | 35.81676 | -83.14321 |
| Heiskell | TN | 36.08182 | -84.05398 |
| Hurricane Mills | TN | 35.97117 | -87.78197 |
| Joelton | TN | 36.31311 | -86.86528 |
| Kodak | TN | 35.97453 | -83.62684 |
| Nashville | TN | 36.16228 | -86.77430 |
| Pioneer | TN | 36.41758 | -84.31410 |
| Chappell Hill | TX | 30.14153 | -96.25672 |
| Hankamer | TX | 29.85828 | -94.62686 |
| Lenorah | TX | 32.30456 | -101.87625 |
| Maxwell | TX | 29.88190 | -97.79564 |
| Orla | TX | 31.82501 | -103.90901 |
| Pecos | TX | 31.42541 | -103.49529 |
| Prairie Hill | TX | 30.24882 | -96.37719 |
| Roans Prairie | TX | 30.58365 | -95.94332 |
| Wall | TX | 31.37435 | -100.30366 |
| Chesterfield | VA | 37.37779 | -77.50467 |
| Clear Brook | VA | 39.25649 | -78.09611 |
| Cross Junction | VA | 39.32038 | -78.29334 |
| Doswell | VA | 37.86014 | -77.46415 |
| Drewryville | VA | 36.71571 | -77.30636 |
| Gladstone | VA | 37.54681 | -78.84946 |
| Gum Spring | VA | 37.77553 | -77.89681 |
| Henrico | VA | 37.62948 | -77.51890 |
| Lambsburg | VA | 36.58541 | -80.76118 |
| Lanexa | VA | 37.42376 | -76.90108 |
| Providence Forge | VA | 37.44243 | -77.04396 |
| Quinton | VA | 37.53279 | -77.11544 |
| Raphine | VA | 37.93735 | -79.23281 |
| Rockville | VA | 37.72598 | -77.67832 |
| Rosedale | VA | 36.95928 | -81.93124 |
| Ruther Glen | VA | 37.94088 | -77.46186 |
| Skippers | VA | 36.61182 | -77.54665 |
| Townsend | VA | 37.18498 | -75.95847 |
| Troy | VA | 37.95097 | -78.24639 |
| Woodford | VA | 38.11319 | -77.40887 |
| Colgate | WI | 43.19283 | -88.20677 |
| Franksville | WI | 42.76002 | -87.91341 |
| Larsen | WI | 44.19165 | -88.62400 |
| Ivydale | WV | 38.31010 | -81.70457 |
| Kearneysville | WV | 39.38816 | -77.88555 |
| Mount Nebo | WV | 39.60230 | -79.70783 |
| Teays | WV | 38.44176 | -81.95291 |

## 5. Excluded Stations
| OPIS ID | Name | Address | City | State | Price | Reason |
|---|---|---|---|---|---|---|
| 912 | PETRO STOPPING CENTER #319 | I-20/59, EXIT 100 | Mc Calla | AL | $3.12566666 | Location not found |
| 52383 | FLYING J TRAVEL PLAZA #601 | I-20/I-59, EXIT 104 | Mc Calla | AL | $3.17066666 | Location not found |
| 67331 | LOVES TRAVEL STOP #227 | I-20 /I-59, EXIT 100 & SR-216 | Mc Calla | AL | $3.159 | Location not found |
| 71329 | SPEEDWAY #1439 | I-20 Exit 100 | Mc Calla | AL | $2.90233333 | Location not found |
| 68009 | CIRCLE K #2741779 | US-270, EXIT 2 | Hot Springs National Park | AR | $3.369 | Location not found |
| 68008 | FAST LANE #3 | US-64 & US-49 | Mc Crory | AR | $3.399 | Location not found |
| 72291 | Union 76 | US-129 | Mc Alpin | FL | $3.659 | Location not found |
| 341 | TA JACKSONVILLE SOUTH TRAVEL CENTER | I-95, EXIT 329 | Saint Johns | FL | $3.469 | Location not found |
| 52680 | PILOT TRAVEL CENTERS #91 | I-95, EXIT 329 | Saint Johns | FL | $3.424 | Location not found |
| 7471 | ROAD RANGER #185 | I-55, EXIT 145 & US-136 | Mc Lean | IL | $3.349 | Location not found |
| 64523 | SKY CITY TRAVEL CENTER | I-40, EXIT 102 NORTH | Pueblo Of Acoma | NM | $3.28066666 | Location not found |
| 1599 | ONVO TRAVEL PLAZA | I-81, EXIT 10 | Mc Graw | NY | $3.439 | Location not found |
| 62841 | SPEEDWAY #9912 | I-81, EXIT 10 | Mc Graw | NY | $4.309 | Location not found |
| 52676 | PILOT TRAVEL CENTERS #336 | I-80, EXIT 97 & US-219 | Du Bois | PA | $4.034 | Location not found |
| 64274 | RUTTERS #53 | I-83, EXIT 32 & SR-382 | Etters | PA | $3.999 | Location not found |

## 6. Per-State Station Coverage
| State | Total Stations | Geocoded | Excluded | Coverage % |
|---|---|---|---|---|
| AL | 162 | 158 | 4 | 97.5% |
| AR | 116 | 114 | 2 | 98.3% |
| AZ | 132 | 132 | 0 | 100.0% |
| CA | 8 | 8 | 0 | 100.0% |
| CO | 99 | 99 | 0 | 100.0% |
| CT | 25 | 25 | 0 | 100.0% |
| DE | 15 | 15 | 0 | 100.0% |
| FL | 189 | 186 | 3 | 98.4% |
| GA | 284 | 284 | 0 | 100.0% |
| IA | 220 | 220 | 0 | 100.0% |
| ID | 61 | 61 | 0 | 100.0% |
| IL | 329 | 328 | 1 | 99.7% |
| IN | 212 | 212 | 0 | 100.0% |
| KS | 127 | 127 | 0 | 100.0% |
| KY | 120 | 120 | 0 | 100.0% |
| LA | 196 | 196 | 0 | 100.0% |
| MA | 44 | 44 | 0 | 100.0% |
| MD | 64 | 64 | 0 | 100.0% |
| ME | 30 | 30 | 0 | 100.0% |
| MI | 164 | 164 | 0 | 100.0% |
| MN | 175 | 175 | 0 | 100.0% |
| MO | 249 | 249 | 0 | 100.0% |
| MS | 141 | 141 | 0 | 100.0% |
| MT | 44 | 44 | 0 | 100.0% |
| NC | 195 | 195 | 0 | 100.0% |
| ND | 59 | 59 | 0 | 100.0% |
| NE | 111 | 111 | 0 | 100.0% |
| NH | 23 | 23 | 0 | 100.0% |
| NJ | 112 | 112 | 0 | 100.0% |
| NM | 107 | 106 | 1 | 99.1% |
| NV | 71 | 71 | 0 | 100.0% |
| NY | 113 | 111 | 2 | 98.2% |
| OH | 262 | 262 | 0 | 100.0% |
| OK | 182 | 182 | 0 | 100.0% |
| OR | 29 | 29 | 0 | 100.0% |
| PA | 217 | 215 | 2 | 99.1% |
| RI | 2 | 2 | 0 | 100.0% |
| SC | 181 | 181 | 0 | 100.0% |
| SD | 62 | 62 | 0 | 100.0% |
| TN | 162 | 162 | 0 | 100.0% |
| TX | 776 | 776 | 0 | 100.0% |
| UT | 93 | 93 | 0 | 100.0% |
| VA | 198 | 198 | 0 | 100.0% |
| VT | 16 | 16 | 0 | 100.0% |
| WA | 52 | 52 | 0 | 100.0% |
| WI | 295 | 295 | 0 | 100.0% |
| WV | 38 | 38 | 0 | 100.0% |
| WY | 64 | 64 | 0 | 100.0% |

## 7. Price Statistics (Geocoded Stations)
- **Minimum Retail Price**: $2.6873/gal
- **Maximum Retail Price**: $6.3990/gal
- **Mean Retail Price**: $3.4133/gal
- **Median Retail Price**: $3.3923/gal
- **Price Outliers (> 4σ)**: 17
