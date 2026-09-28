import react from "@vitejs/plugin-react";
import {fileURLToPath, URL} from "node:url";
import {defineConfig} from "vite";

// Dev: `npm run dev` on :5173 proxies the API on :8000. Prod: `npm run build` -> dist/, served by the API at "/".
export default defineConfig({
  plugins: [react()],
  resolve: {alias: {"@": fileURLToPath(new URL("./src", import.meta.url))}},
  build: {outDir: "dist", emptyOutDir: true, rollupOptions: {output: {manualChunks: {maplibre: ["maplibre-gl"], chart: ["chart.js"], react: ["react", "react-dom", "react-router-dom", "@tanstack/react-query"]}}}},
  server: {port: 5173, proxy: {"/api": "http://127.0.0.1:8000", "/media": "http://127.0.0.1:8000"}},
  test: {globals: true, environment: "jsdom", setupFiles: ["src/test/setup.ts"], include: ["src/**/*.test.ts", "src/**/*.test.tsx"]},
});
