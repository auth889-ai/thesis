# Fix 14_research_bangla (QA table rank 14)

- Change: the Research evidence page, its verdict, and the lab header, menu and footer go through the translation files (en, bn). Still English in Bangla: the experiment's own labels and scenario texts read from its run files (for example 'reactive routing (current travel times)', 'SIMULATED V2X EMULATOR'); they are shown as recorded
- Regression test: frontend/src/features/results/verdict.test.ts (2 new), frontend/src/app/labNav.test.ts
- Same QA check against the hosted app: **before 8/8 passed, after 8/8 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F12-desktop-dhaka-1 | pass | pass | 34.4 s |  |
| F12-desktop-dhaka-2 | pass | pass | 34.4 s |  |
| F12-desktop-dhaka-3 | pass | pass | 34.3 s |  |
| F12-desktop-los_angeles-1 | pass | pass | 36.9 s |  |
| F12-phone-dhaka-1 | pass | pass | 34.4 s |  |
| F12-phone-dhaka-2 | pass | pass | 34.4 s |  |
| F12-phone-dhaka-3 | pass | pass | 34.3 s |  |
| F12-phone-los_angeles-1 | pass | pass | 36.9 s |  |

Note: the Tour passed before too; rank 14 is about the text. English text nodes on the Bangla Tour: before 10 including "Does smart routing help?" and the page's own sentences; after, only the run files' labels (see text.english in each after run).
