import {defineConfig} from "vite";

// Dev: `npm run dev` on :5173 proxies the API on :8000. Prod: `npm run build` -> dist/, served by the API.
export default defineConfig({
  root: ".",
  build: {outDir: "dist", emptyOutDir: true},
  server: {port: 5173, proxy: {"/api": "http://127.0.0.1:8000", "/media": "http://127.0.0.1:8000"}},
  test: {environment: "node", include: ["src/**/*.test.js", "src/**/*.test.ts"]},
});
