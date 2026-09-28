# TrafficTwin web app

React 19 + TypeScript, built with Vite, tested with Vitest and Testing Library. Data fetching goes through
TanStack Query; maps are MapLibre GL; charts are Chart.js. The API client types are generated from the
backend's OpenAPI document.

```
npm install            # toolchain
npm run dev            # http://127.0.0.1:5173 with live reload; /api and /media are proxied to the API on :8000
npm run build          # production bundle -> dist/ (the API serves it at "/" when present)
npm test               # unit tests (Vitest, jsdom)
npm run typecheck      # strict TypeScript
npm run api:types      # regenerate src/lib/api.types.d.ts from openapi.json (`make openapi` exports it)
```

## Layout

```
src/
  main.tsx                 entry: QueryClient + Router
  app/                     shell (sidebar, page header) and the route table
  components/              shared UI: ui primitives, MapView, LineChart, Tabs, Steps
  lib/                     api client, formatting, basemap style, chart defaults
  features/<domain>/       one folder per page, each with its page component, small sub-components,
                           hooks, pure helpers and their tests, and a scoped stylesheet
    assistant/             Today: goals, plans, approvals, audit
    mobility/              trip analysis, route map, "leave when?" commute planner
    forecast/              network forecast map, inspector, road chart, models, validation, training, data
    twin/                  control room: fresh execution and recorded replay
    results/               the evidence page
    references/            every paper, dataset, standard and tool used
    system/                pipeline and computed research status
  styles/global.css        design tokens and primitives (light and dark)
```

Rules: a file does one thing and stays under 200 lines (pinned by a backend test); pages render only what
the API returns, with its provenance; no number on any page is a constant.
