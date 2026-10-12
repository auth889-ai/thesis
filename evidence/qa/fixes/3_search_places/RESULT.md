# Fix 3_search_places (QA table rank 3)

- Change: searchRows offers places anywhere in a city with a whole-city routing server; 'add this city' is held back while a place lookup is due or the city list is still loading (attempt 1: places filtered to the built box only, 0/8; attempt 2: race with the instant add row, 4/8; attempt 3 here)
- Regression test: frontend/src/app/search.test.ts (2 new), frontend/src/app/Search.test.tsx (2)
- Same QA check against the hosted app: **before 0/8 passed, after 8/8 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F1-desktop-dhaka-1 | fail | pass | 7.8 s |  |
| F1-desktop-dhaka-2 | fail | pass | 7.8 s |  |
| F1-desktop-dhaka-3 | fail | pass | 7.7 s |  |
| F1-desktop-los_angeles-1 | fail | pass | 10.3 s |  |
| F1-phone-dhaka-1 | fail | pass | 11.3 s |  |
| F1-phone-dhaka-2 | fail | pass | 7.7 s |  |
| F1-phone-dhaka-3 | fail | pass | 7.7 s |  |
| F1-phone-los_angeles-1 | fail | pass | 14.3 s |  |
