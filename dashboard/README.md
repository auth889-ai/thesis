# DhakaFlow dashboard

    cd dashboard/backend && pip install fastapi uvicorn && python main.py
    open http://127.0.0.1:8000          # UI
    open http://127.0.0.1:8000/api/docs # generated OpenAPI

## Structure

```
dashboard/
├── backend/
│   ├── config.py     every evidence file + the command that regenerates it
│   ├── schemas.py    Pydantic v2 response contract
│   ├── readers.py    one function per panel: read the file, shape it, attach provenance
│   ├── main.py       routes + the SSE stream
│   └── tests/
└── frontend/         no build step: HTML + JS from CDNs
```

Four backend files, deliberately. A domain-per-package layout (`traffic/`, `forecast/`, … each with
`router.py`, `service.py`, `schemas.py`) is the right shape when domains own database models and
real business logic — that is what `fastapi-best-practices` is written for. Here every domain does
one thing: open a file the research pipeline produced. Splitting that across 24 directories produced
33 files averaging 24 lines each, which is harder to read than the code it contains.

## Two rules the UI follows

1. **Nothing is invented.** Each response carries `provenance`: the source file, the command that
   regenerates it, and a reality label (`REAL_LIVE`, `REAL`, `SIMULATED`). A panel with no evidence
   returns `available: false` and the command to produce it, instead of an empty chart.
2. **Stale data is not shown as live.** `/api/health` and the SSE stream carry recorder freshness;
   the UI marks itself disconnected rather than leaving old numbers on screen.

## Real-time

Server-Sent Events, not WebSocket: the dashboard is display-only, so a bidirectional socket adds
complexity for nothing. SSE is plain HTTP, `EventSource` reconnects by itself, the server sends a
`retry:` backoff hint, and the payload is a diff (freshness + latest level per corridor, ~700 bytes)
rather than a full snapshot.

## Open source used, with thanks

| Component | License | Used for |
|---|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | the API |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3 | ASGI server |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | response contracts |
| [MapLibre GL JS](https://github.com/maplibre/maplibre-gl-js) | BSD-3 | map rendering |
| [Chart.js](https://github.com/chartjs/Chart.js) | MIT | charts |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | ODbL | map tiles |

Architecture informed by [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices),
[sidewalklabs/sumo-web3d](https://github.com/sidewalklabs/sumo-web3d) (diff-streaming rather than
full snapshots) and [vietanhlee/Smart-Traffic-Monitoring-System](https://github.com/vietanhlee/Smart-Traffic-Monitoring-System).
