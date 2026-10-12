# Fix 1_sos_traces (QA table rank 1, 2)

- Change: research/sos/traces added to the hosted package (folder list moved to infra/app/package_paths.txt)
- Regression test: backend/tests/test_hosted_package.py::test_crash_sos_traces_are_packaged (fails with the traces left out)
- Same QA check against the hosted app: **before 0/16 passed, after 16/16 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F11-desktop-dhaka-1 | fail | pass | 48.4 s |  |
| F11-desktop-dhaka-2 | fail | pass | 46.6 s |  |
| F11-desktop-dhaka-3 | fail | pass | 47.1 s |  |
| F11-desktop-los_angeles-1 | fail | pass | 51.3 s |  |
| F11-phone-dhaka-1 | fail | pass | 46.8 s |  |
| F11-phone-dhaka-2 | fail | pass | 59.8 s |  |
| F11-phone-dhaka-3 | fail | pass | 46.4 s |  |
| F11-phone-los_angeles-1 | fail | pass | 52.6 s |  |
| F9-desktop-dhaka-1 | fail | pass | 35.8 s |  |
| F9-desktop-dhaka-2 | fail | pass | 35.7 s |  |
| F9-desktop-dhaka-3 | fail | pass | 35.5 s |  |
| F9-desktop-los_angeles-1 | fail | pass | 38.1 s |  |
| F9-phone-dhaka-1 | fail | pass | 35.3 s |  |
| F9-phone-dhaka-2 | fail | pass | 35.4 s |  |
| F9-phone-dhaka-3 | fail | pass | 38.1 s |  |
| F9-phone-los_angeles-1 | fail | pass | 37.7 s |  |
