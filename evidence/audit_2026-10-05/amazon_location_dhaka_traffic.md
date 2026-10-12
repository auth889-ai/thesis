# Does Amazon Location return traffic for Dhaka? — method and conclusion

Raw API responses are not kept (AWS Service Terms 82.4(a)); this file records only what was done and what was found.

## Method
- When: 2026-10-04, 23:18–23:33 UTC (05:18–05:33 in Dhaka, 16:18 in Los Angeles, 01:18 on 5 October in Berlin).
- Service: Amazon Location Routes API (`geo-routes` CalculateRoutes), region us-west-2, travel mode Car, pricing bucket Core.
- Requests: 13 in total.
- Routes: Dhaka Farmgate → Shahbagh; Dhaka Airport → Mohakhali; Los Angeles, a US-101 stretch through Hollywood;
  Berlin, a stretch of the A100. The two non-Dhaka routes are controls.
- Settings varied per route (4 routes × 3 = 12 requests): traffic on with departure now; traffic off with departure now;
  traffic on with departure exactly one week later.
- One further request: Dhaka Farmgate → Shahbagh, traffic on, departure Thursday 2026-10-08 18:00 Dhaka time (evening peak).
- Read from each response: the route duration and, per span, Duration, TypicalDuration and BestCaseDuration.
- Second, independent check: the 94 Amazon-derived samples already stored for Dhaka in `results/live/observatory.sqlite`
  (2026-10-03 12:38 UTC to 2026-10-04 04:00 UTC, i.e. 18:38 to 10:00 Dhaka time, both peaks included).

## Finding
- Dhaka returned the identical duration in every case: Farmgate → Shahbagh 251 s with traffic on, traffic off, one week
  ahead and at the Thursday evening peak, with typical = best case = 251 s; Airport → Mohakhali 692 s in all three settings.
- The controls varied: Los Angeles 548 s (traffic on), 417 s (traffic off), 519 s (one week ahead; typical 519, best case
  417). Berlin 497 s (traffic on, three incidents reported), 515 s (traffic off), 490 s (one week ahead).
- Stored samples: each of the 12 Dhaka corridors has exactly one distinct speed across all 94 samples. Over the same period
  the 13 Nairobi corridors each show many distinct speeds.
- AWS's "Data quality and coverage" page lists traffic coverage for the United States and Germany and has no row for
  Bangladesh (read 2026-10-04).

## Conclusion
For Dhaka, Amazon Location returns a single free-flow travel time per route and no traffic information, live or
historical. Values obtained from it for Dhaka are free-flow estimates and must not be labelled live, typical-by-time-of-day
or observed.

## Not established
- Which geolocation provider backs the Routes API for this account (the response names none; no route calculator
  resource exists in the account).
- Whether this holds for the rest of Bangladesh; only two Dhaka routes and the twelve stored corridors were checked.
