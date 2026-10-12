# Fix 7_recorded (QA table rank 7)

- Change: DhaTraX MANIFEST.json, replay/ and the two Traffic_Analysis summaries packaged (CC BY 4.0); 'on this computer' wording replaced. The first deploy packaged the manifest without the summaries and broke whole-city routes (500) for about 16 min (23:33–23:49 +06) until redeployed; a test now runs every recorded reader. The QA check now requires recorded vehicles, not only a reason
- Regression test: backend/tests/test_hosted_package.py::test_recorded_replay_files_are_packaged, ::test_every_recorded_reader_reads_only_packaged_files
- Same QA check against the hosted app: **before 8/8 passed, after 6/6 passed**

| Run | Before | After | After time | After reason |
|---|---|---|---|---|
| F6-desktop-dhaka-1 | pass | pass | 16.3 s |  |
| F6-desktop-dhaka-2 | pass | pass | 16.3 s |  |
| F6-desktop-dhaka-3 | pass | pass | 16.4 s |  |
| F6-phone-dhaka-1 | pass | pass | 16.4 s |  |
| F6-phone-dhaka-2 | pass | pass | 16.3 s |  |
| F6-phone-dhaka-3 | pass | pass | 16.4 s |  |

Note: "before" counts are the original script's verdicts, which passed these runs because a reason was shown ("No recorded traffic is ready for Dhaka on this computer"). On review they were failures (QA_TABLE.md rank 7). The tightened check (recorded vehicles must arrive) would have failed all 6.
