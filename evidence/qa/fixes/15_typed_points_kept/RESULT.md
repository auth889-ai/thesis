# Fix 15_typed_points_kept (QA table rank owner item)

- Change: Home clears a trip only on a switch from one city to another, never when the city list first arrives (useCityChange)
- Regression test: frontend/src/features/today/useCityChange.test.ts; new QA check F14 (a place sent to Home survives the city loading)
- Same QA check against the hosted app: **before 0/4 passed, after 6/6 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F14-desktop-dhaka-1 | fail | pass | 13.8 s |  |
| F14-desktop-dhaka-2 | fail | pass | 13.9 s |  |
| F14-desktop-dhaka-3 | fail | pass | 13.9 s |  |
| F14-phone-dhaka-1 | fail | pass | 14.4 s |  |
| F14-phone-dhaka-2 | fail | pass | 13.6 s |  |
| F14-phone-dhaka-3 | fail | pass | 13.8 s |  |
