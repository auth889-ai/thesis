import react from "@vitejs/plugin-react";
import {fileURLToPath, URL} from "node:url";
import {defineConfig} from "vite";
import {VitePWA} from "vite-plugin-pwa";
import wasm from "vite-plugin-wasm";

// Dev: `npm run dev` on :5173 proxies the API on :8000. Prod: `npm run build` -> dist/, served by the API at "/app/"
// (the map app, frontend/map, is at "/"; its menus open these pages).
export default defineConfig({
  base: "/app/",
  plugins: [react(), wasm(), VitePWA({          // wasm: Ferrostar's core is Rust compiled to WebAssembly (as in its own build); top-level await is native at the esnext target
   strategies: "injectManifest", srcDir: "src", filename: "sw.ts", registerType: "prompt", injectRegister: false,
    manifest: {name: "TrafficTwin", short_name: "TrafficTwin", description: "Your city, now and in an hour.", theme_color: "#3b1f1a", background_color: "#f6f1ea", display: "standalone", start_url: "/app/", scope: "/app/", icons: [{src: "/app/icon.svg", sizes: "any", type: "image/svg+xml"}]},
    injectManifest: {globPatterns: ["**/*.{js,css,html,svg,png,json,pbf,wasm}"], globIgnores: ["photos/**"], maximumFileSizeToCacheInBytes: 6 * 1024 * 1024},
    devOptions: {enabled: true, type: "module"}})],
  resolve: {alias: {"@": fileURLToPath(new URL("./src", import.meta.url))}},
  build: {target: "esnext", outDir: "dist", emptyOutDir: true, rollupOptions: {output: {manualChunks: {maplibre: ["maplibre-gl"], chart: ["chart.js"], react: ["react", "react-dom", "react-router-dom", "@tanstack/react-query"]}}}},
  server: {port: 5173, proxy: {"/api": "http://127.0.0.1:8000", "/media": "http://127.0.0.1:8000"}},
  test: {globals: true, environment: "jsdom", setupFiles: ["src/test/setup.ts"], include: ["src/**/*.test.ts", "src/**/*.test.tsx"]},
});
