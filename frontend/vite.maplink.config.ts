import {fileURLToPath, URL} from "node:url";
import {defineConfig} from "vite";
import wasm from "vite-plugin-wasm";

// The map app's link to our features (src/maplink): one ES module at frontend/map/public/tt/maplink.js, which Quasar copies into the
// map app's build. Built with the same toolchain as the React pages (esnext, Ferrostar's WebAssembly); Headway's build is not touched.
export default defineConfig({
  plugins: [wasm()],
  resolve: {alias: [{find: /^maplibre-gl$/, replacement: fileURLToPath(new URL("./src/maplink/maplibreShim.ts", import.meta.url))},
    {find: "@", replacement: fileURLToPath(new URL("./src", import.meta.url))}]},
  base: "/tt/",
  build: {target: "esnext", outDir: "map/public/tt", emptyOutDir: true, copyPublicDir: false,
    lib: {entry: fileURLToPath(new URL("./src/maplink/index.ts", import.meta.url)), formats: ["es"], fileName: () => "maplink.js"}},
});
