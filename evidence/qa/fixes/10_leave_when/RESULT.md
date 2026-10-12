# Fix 10_leave_when (QA table rank 10)

- Change: Leave when: the map-speed time is one plain sentence with its tag and How we know link; network source and basis removed from the everyday panel (they stay on Research)
- Regression test: frontend/src/features/today/LeaveWhen.test.tsx; QA check F5 now fails on developer wording
- Same QA check against the hosted app: **before 6/8 passed, after 8/8 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F5-desktop-dhaka-1 | pass | pass | 6.3 s |  |
| F5-desktop-dhaka-2 | pass | pass | 6.3 s |  |
| F5-desktop-dhaka-3 | pass | pass | 6.3 s |  |
| F5-desktop-los_angeles-1 | fail | pass | 9.0 s |  |
| F5-phone-dhaka-1 | pass | pass | 6.4 s |  |
| F5-phone-dhaka-2 | pass | pass | 6.3 s |  |
| F5-phone-dhaka-3 | pass | pass | 6.4 s |  |
| F5-phone-los_angeles-1 | fail | pass | 10.3 s |  |

Note: "before" counts are the original check, which did not look for developer wording; the Dhaka passes there still showed "SUMO netconvert" (QA_TABLE.md rank 10). The 2 LA failures were the city-switch crash (rank 4).
