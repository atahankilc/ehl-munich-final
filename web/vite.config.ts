import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// The API (FastAPI, `api/`) runs on 127.0.0.1:8600; in dev Vite proxies to it. Localhost only (AGENTS rule 1).
const API = "http://127.0.0.1:8600";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { host: "127.0.0.1", port: 5173, proxy: { "/api": API, "/models": API } },
  preview: { host: "127.0.0.1", port: 4173, proxy: { "/api": API, "/models": API } },
  build: { outDir: "dist", chunkSizeWarningLimit: 2000 },
});
