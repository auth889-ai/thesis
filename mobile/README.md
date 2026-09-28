# TrafficTwin mobile

Expo (React Native) + TypeScript. Three screens on the same API as the web app: **Trip** (where to → ETA now and at
departure, the recommended route, the honest data label), **Forecast** (the sensor network's predicted state) and
**Results** (does smart routing help — the current evidence, computed by the backend).

```
npm install
npm run api:types      # typed API client from ../frontend/openapi.json (export it with `make openapi`)
npm start              # Expo dev server; scan the QR with Expo Go, or press a / i for an emulator
npm run typecheck
```

Point `expo.extra.apiUrl` in `app.json` at the API. On a phone that is the machine's LAN address (http://192.168.x.y:8000),
never localhost. Start the API first: `make app` from the repository root.
