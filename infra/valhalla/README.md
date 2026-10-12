# Valhalla routing server (whole-city routes)

One on-demand EC2 instance in ap-south-1 runs the official Valhalla image (MIT) once per OpenStreetMap extract
(Geofabrik, ODbL): Dhaka from `asia/bangladesh` on port 8002, Los Angeles from `north-america/us/california/socal`
on port 8003. Licences: `third_party/SOURCES.md`, "Whole-city routing". The security group admits the launching
machine's public IP only.

| | |
|---|---|
| Instance | t3.xlarge (4 vCPU, 16 GB), 60 GB gp3, on-demand (a server must stay up; spot is for training and sweeps) |
| Hours | 48 at most: the machine shuts itself down at 48 h (`user-data.sh` watchdog), `--instance-initiated-shutdown-behavior terminate` |
| Cost | approved 2026-10-06, rates read the same day with `aws pricing get-products` (regionCode ap-south-1, recorded in `evidence/routing/valhalla_instance.json`): t3.xlarge on-demand Linux **$0.1792/h** → 48 h = $8.60; gp3 $0.0912 per GB-month → 60 GB for 48 h ≈ $0.36; **total ≈ $8.96 for the 48 h**. **S3:** Standard, first 50 TB, $0.025 per GB-month; the saved tiles are about 2 GB, so about **$0.05 per month** |
| Tags | `project=dhakaflow`, `phase=routing` on the instance, the volume, the bucket and every object |

```bash
aws login                                             # the owner's session
infra/valhalla/launch.sh --approved                   # first time: downloads the extracts, builds the tiles (1-2 h), then saves them to S3
infra/valhalla/launch.sh --approved --from-s3         # later: a new server from the saved tiles, ready in minutes
infra/valhalla/stop.sh                                # terminates the routing instance(s); the tiles stay in S3
```

`launch.sh` prints the instance id, the public IP and the two environment variables to put in `.env`
(`TRAFFICTWIN_VALHALLA_URL_DHAKA`, `TRAFFICTWIN_VALHALLA_URL_LOS_ANGELES`); the backend reads them through
`core/common/credentials.py`. On the server, `/srv/valhalla/SOURCES.txt` holds each extract's URL, sha256 and
Last-Modified, `TILES.txt` the sha256 of each saved tile file; `/var/log/dhakaflow.log` the build log. Copy both
text files into `evidence/routing/` once READY (`scp` or the console), as the evidence of what was built.
`setup-iam.sh` creates the instance profile `dhakaflow-valhalla-profile`, allowed to read and write the routing
bucket `dhakaflow-routing-<account>` only.
