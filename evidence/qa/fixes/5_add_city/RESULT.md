# Fix 5_add_city (QA table rank 5)

- Change: duckdb installed on the hosted app; the DuckDB connection is created with a home directory and httpfs loaded (the service has no HOME); a failed search shows a plain translated sentence, the exception stays in 'detail'. The QA check now waits as long as the page says (a new name can take about a minute) and reads the result labels. Found in this re-run: a build refused by the daily limit (429) left the page silent; fixed in the next deploy and checked in the final matrix
- Regression test: backend/tests/test_hosted_package.py: every backend requirement installed; search failure is a code; connects without HOME with httpfs loaded
- Same QA check against the hosted app: **before 0/8 passed, after 8/8 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F2-desktop-dhaka-1 | fail | pass | 14.3 s |  |
| F2-desktop-dhaka-2 | fail | pass | 14.2 s |  |
| F2-desktop-dhaka-3 | fail | pass | 14.0 s |  |
| F2-desktop-los_angeles-1 | fail | pass | 14.4 s |  |
| F2-phone-dhaka-1 | fail | pass | 14.2 s |  |
| F2-phone-dhaka-2 | fail | pass | 14.1 s |  |
| F2-phone-dhaka-3 | fail | pass | 14.4 s |  |
| F2-phone-los_angeles-1 | fail | pass | 14.1 s |  |

Attempts kept: attempt1_no_home_dir (0/8, DuckDB could not install httpfs without HOME), attempt2_failed (0/8, SET home_directory after connect is ignored by the automatic install), attempt3_check_waited_30s, attempt4_check_wrong_locator (the search worked; the check looked for list items instead of the result labels).
