# TrafficTwin web app

Plain ES modules (no framework), built and tested with Vite, Vitest and TypeScript. The API client types are
generated from the backend's OpenAPI document.

```
npm install            # toolchain
npm run dev            # http://127.0.0.1:5173 with live reload; /api and /media are proxied to the API on :8000
npm run build          # production bundle -> dist/ (the API serves it when present)
npm test               # unit tests (Vitest)
npm run typecheck      # TypeScript over the JS sources (allowJs)
npm run api:types      # regenerate src/services/api.types.d.ts from openapi.json
```

Layout: `index.html`, `src/app.js` (hash router), `src/pages/` (one file per page; `legacy/` holds the older pages),
`src/components/`, `src/services/` (api client, basemap, formatting, streaming), `src/styles/`.
