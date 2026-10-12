# Fix 9_bangla_turns (QA table rank 9)

- Change: the spoken Bangla turn no longer reads our own sentence back as a road name; recognised by its text because Ferrostar's core copies the route (attempt 2 relied on a mark the copy dropped, 0/6)
- Regression test: frontend/src/features/today/bannerText.test.ts (3); QA check F4 fails on a doubled phrase
- Same QA check against the hosted app: **before 6/8 passed, after 6/6 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F4-desktop-dhaka-1 | pass | pass | 34.2 s |  |
| F4-desktop-dhaka-2 | pass | pass | 34.7 s |  |
| F4-desktop-dhaka-3 | pass | pass | 33.2 s |  |
| F4-phone-dhaka-1 | pass | pass | 33.2 s |  |
| F4-phone-dhaka-2 | pass | pass | 33.2 s |  |
| F4-phone-dhaka-3 | pass | pass | 32.7 s |  |

Note: "before" counts are the original check, which did not look for a doubled phrase; all 6 Dhaka passes logged "হালকা বাঁয়ে হালকা বাঁয়ে যান-এ যান" (QA_TABLE.md rank 9). The 2 LA failures were the city-switch crash (rank 4).
