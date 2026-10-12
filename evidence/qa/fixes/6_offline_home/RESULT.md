# Fix 6_offline_home (QA table rank 6)

- Change: the trip pack also keeps the answers Home needs to open (city list, the visitor's profile) via api.packUrls; the existing pack fallback serves them offline (attempt 1 ran while whole-city routing answered 500 and is kept as invalid)
- Regression test: frontend/src/lib/packUrls.test.ts
- Same QA check against the hosted app: **before 0/8 passed, after 8/8 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F10-desktop-dhaka-1 | fail | pass | 31.0 s |  |
| F10-desktop-dhaka-2 | fail | pass | 29.5 s |  |
| F10-desktop-dhaka-3 | fail | pass | 29.0 s |  |
| F10-desktop-los_angeles-1 | fail | pass | 40.7 s |  |
| F10-phone-dhaka-1 | fail | pass | 30.1 s |  |
| F10-phone-dhaka-2 | fail | pass | 28.1 s |  |
| F10-phone-dhaka-3 | fail | pass | 26.5 s |  |
| F10-phone-los_angeles-1 | fail | pass | 41.0 s |  |
