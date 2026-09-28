# Frontend

The existing browser application uses HTML, CSS and JavaScript ES modules.
No framework rewrite or new build step was introduced by the directory migration.

- `index.html`: document and navigation shell.
- `app.js`: page registration and navigation.
- `pages/`: the four primary scientific screens.
- `pages/legacy/`: earlier prototype/research screens, preserved with working routes.
- `components/`: shared controls and evidence panels, not full pages.
- `services/`: API requests, event stream, formatting and basemap access.
- `styles/`: design tokens and application styles.

Start `make app` from the repository root. FastAPI serves this directory at `/static`
and `index.html` at `/`. Relative module imports follow the grouped layout. External CDN assets
and basemaps can still require internet access.

The primary surfaces are System, Prediction, Control Room and Results. Legacy
pages remain available during migration; moving files does not make their claims
validated. Control Room has separate Fresh execution and Recorded replay modes.
Only Fresh execution launches the scientific worker; replay reads persisted logs.
