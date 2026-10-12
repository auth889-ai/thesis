# Fix 11_sim_other_city (QA table rank 11)

- Change: when another city's simulation holds the site, a clear warning note says so and names the button; the 3D City check now requires that note (it passed before while LA showed Dhaka's run and empty numbers). Checked in the final matrix
- Regression test: QA check F13 (other_city_note)
- Same QA check against the hosted app: **before 2/2 passed, after 2/2 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F13-desktop-los_angeles-1 | pass | pass | 5.1 s |  |
| F13-phone-los_angeles-1 | pass | pass | 5.1 s |  |

Note: the original check passed these runs; on review they were failures (QA_TABLE.md rank 11). After: other_city_note is true on both runs.
