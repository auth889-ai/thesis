# Fix 4_city_switch (QA table rank 4)

- Change: removed maps ignored: components/mapReady.ts (whenStyled never draws on a removed map; useMapInstance returns to null on the map's remove event); Home and Emergency map hooks skip a removed map. QA script: route sentence read in the city's own units (miles in LA). F10 in LA still fails until rank 6 is fixed
- Regression test: frontend/src/components/mapReady.test.ts (4 tests)
- Same QA check against the hosted app: **before 18/32 passed, after 6/8 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F10-desktop-los_angeles-1 | fail | fail | 155.8 s | no route sentence after going offline and reloading; no map offline |
| F10-phone-los_angeles-1 | fail | fail | 134.5 s | no route sentence after going offline and reloading; no map offline |
| F3-desktop-los_angeles-1 | fail | pass | 18.0 s |  |
| F3-phone-los_angeles-1 | fail | pass | 17.7 s |  |
| F4-desktop-los_angeles-1 | fail | pass | 42.7 s |  |
| F4-phone-los_angeles-1 | fail | pass | 45.8 s |  |
| F5-desktop-los_angeles-1 | fail | pass | 9.5 s |  |
| F5-phone-los_angeles-1 | fail | pass | 9.3 s |  |
