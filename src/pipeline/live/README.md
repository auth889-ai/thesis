# live/ - real route advice and pilot evidence

This folder is the no-fixed-seed path.

It uses live Google Routes values only at runtime to choose an advisory route.
The evidence files store privacy-preserving request refs, recommendation
metadata, derived congestion state, and real user trip timestamps. They do not
store Google route durations, distances, speed intervals, or geometry.

Commands:

```bash
python live/route_advisor.py --dry-run --corridor farmgate_to_shahbagh
python live/route_advisor.py --live --yes --corridor farmgate_to_shahbagh

python live/user_trip_logger.py start --participant p1 --advice-id <id> --corridor farmgate_to_shahbagh
python live/user_trip_logger.py complete --trip-id <trip_id>
python live/user_trip_logger.py summarize
```

Files:

- `live/results/route_advice.jsonl` - compliant advisory metadata.
- `live/results/pilot_trips.jsonl` - real user-pilot start/complete events.
- `live/results/pilot_metrics.{json,md}` - small-sample pilot summary.

SUMO/MOSAIC remains useful as an appendix stress test. It is not the main
"real" claim.

