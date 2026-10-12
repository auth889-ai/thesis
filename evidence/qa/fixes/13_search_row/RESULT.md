# Fix 13_search_row (QA table rank 13)

- Change: the add-city row no longer prints its group word before 'Add …'. Checked in the final matrix
- Regression test: frontend/src/app/Search.test.tsx (row text)
- Same QA check against the hosted app: **before 0/4 passed, after 4/4 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F1-desktop-dhaka-1 | fail | pass | 7.8 s |  |
| F1-desktop-los_angeles-1 | fail | pass | 10.3 s |  |
| F1-phone-dhaka-1 | fail | pass | 9.3 s |  |
| F1-phone-los_angeles-1 | fail | pass | 13.3 s |  |

Note: before, the rows read "add Add \"Hollywood\" as a city" (and the search failed, rank 3); after, the place rows are offered (see rows in each run).
