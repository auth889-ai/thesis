# Camera-provider qualification — P-LIVE track (opened 2026-08-16)

Provider-neutral `CameraProvider` protocol lives in `dhakaflow/live/providers.py`.
No purchase happens until every checklist item below is verified IN WRITING.

## Qualification checklist (identical for every provider)

| # | Requirement | Why |
|---|---|---|
| 1 | Dhaka/Bangladesh coverage — named cameras, count, locations | No coverage = no purchase |
| 2 | HasStream / stream URL availability (video, not stills) | ByteTrack needs frames in sequence |
| 3 | Automated CV-processing rights, in the contract text | Our whole use is automated analysis |
| 4 | Derived-data retention rights (counts, tracks, figures) | The thesis persists derived data |
| 5 | Thesis publication + public-demo rights | Defense + dashboard |
| 6 | Refresh rate / latency / uptime SLA | Freshness feeds the live API |
| 7 | Pricing incl. trial/academic tier | Budget decision needs numbers |

## A. INRIX — status: OUTREACH_REQUIRED (user action)
- Developer portal: docs.inrix.com/traffic/trafficcameras — Traffic Camera
  Service exists; coverage list not public.
- ACTION (user): request trial via inrix.com developer contact from the IUT
  address; ask checklist items 1-7 verbatim. Template below.

## B. TrafficLand — status: EXTERNAL_CITY_CANDIDATE
- US DOT live video aggregator; role here is CITY-PORTABILITY VALIDATION
  (proving the pipeline ingests true live video), classified
  PROVIDER_INTEGRATION_VALIDATION — never DHAKA_LIVE_CAMERA_VALIDATION.
- ACTION (user): request API pricing/trial. Free 511NY key remains the
  zero-cost alternative for the same validation purpose.

## C. Vizzion — status: DO_NOT_PURCHASE (standing rule)
- Public Asia coverage page lists Hong Kong, Indonesia, Thailand, South Korea,
  Japan only (verified 2026-08-15). Bangladesh absent.
- Purchase permitted ONLY on explicit written confirmation of current Dhaka
  coverage. Foreign-market trial = PROVIDER_INTEGRATION_VALIDATION only.

## Outreach template (send from janaeva@iut-dhaka.edu)

> Subject: Academic trial inquiry — live traffic camera API (Dhaka, Bangladesh)
> We are a university research group building an intelligent traffic-management
> research system for Dhaka. Before any commercial discussion we need written
> answers to: (1) current camera coverage in Dhaka/Bangladesh (count and
> locations); (2) whether live VIDEO streams (not stills) are available via
> API; (3) whether automated computer-vision processing of feeds is permitted;
> (4) whether derived statistics (vehicle counts, trajectories) may be retained
> and published in academic work; (5) public-demo rights; (6) refresh
> rate/latency; (7) pricing including any academic/trial tier.

## Status board

| Provider | Dhaka coverage | Trial | CV rights | Verdict |
|---|---|---|---|---|
| INRIX | UNKNOWN — outreach pending | — | — | QUALIFYING |
| TrafficLand | N/A (external-city role) | — | — | QUALIFYING |
| Vizzion | NOT LISTED (verified) | — | — | DO_NOT_PURCHASE |
| 511NY (free) | N/A (external-city role) | free key | public data | READY fallback |
