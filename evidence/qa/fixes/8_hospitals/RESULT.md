# Fix 8_hospitals (QA table rank 8)

- Change: nearest hospitals leave out animal hospitals (OSM healthcare:speciality=veterinary or the name says so; 2 of 477 in Dhaka) and list a hospital entered twice in OpenStreetMap once (same name within 200 m; 10 entries, found in the final matrix where 'General Medical Hospital' filled two of three places). The ambulance reach result is unchanged: it uses only the 37 emergency=yes hospitals, none veterinary or duplicated. The QA check now fails on an animal hospital; in LA it accepts the plain 'no data'
- Regression test: backend/tests/emergency/test_nearest_people_only.py (4)
- Same QA check against the hosted app: **before 6/8 passed, after 8/8 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F7-desktop-dhaka-1 | pass | pass | 8.4 s |  |
| F7-desktop-dhaka-2 | pass | pass | 7.9 s |  |
| F7-desktop-dhaka-3 | pass | pass | 8.4 s |  |
| F7-desktop-los_angeles-1 | fail | pass | 6.3 s |  |
| F7-phone-dhaka-1 | pass | pass | 8.4 s |  |
| F7-phone-dhaka-2 | pass | pass | 7.9 s |  |
| F7-phone-dhaka-3 | pass | pass | 8.4 s |  |
| F7-phone-los_angeles-1 | fail | pass | 6.3 s |  |

Note: "before" counts are the original check, which did not look for animal hospitals; all 6 Dhaka passes listed "Vet-RX" (QA_TABLE.md rank 8). After: Module General Hospital (3 min, 0.4 km), General Medical Hospital (4 min, 0.7 km), PG Outdoor (5 min, 0.7 km).
