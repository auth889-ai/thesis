# Fix 12_bangla_numbers (QA table rank 12)

- Change: numbers in messages are written in the language's own digits; units translated (কিমি, মাইল); Bangla clock times on a 24-hour clock; 'গাড়ি নিয়ে' instead of 'গাড়ি-এ'. Checked in the final matrix: the Bangla route, progress, hospital and Leave when sentences hold no Latin digits, km, min or AM/PM
- Regression test: frontend/src/i18n/banglaNumbers.test.ts (2)
- Same QA check against the hosted app: **before 6/6 passed, after 6/6 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F3-desktop-dhaka-1 | pass | pass | 12.8 s |  |
| F3-desktop-dhaka-2 | pass | pass | 13.0 s |  |
| F3-desktop-dhaka-3 | pass | pass | 13.9 s |  |
| F3-phone-dhaka-1 | pass | pass | 13.1 s |  |
| F3-phone-dhaka-2 | pass | pass | 13.0 s |  |
| F3-phone-dhaka-3 | pass | pass | 12.6 s |  |

Note: pass/fail here is the route check, which passed before too; rank 12 is about the text. Before: "গাড়ি-এ ১২.১ km যেতে প্রায় 54 মিনিট"; after: "গাড়ি নিয়ে ১২.১ কিমি যেতে প্রায় ৫৪ মিনিট" (see each run's sentence).
