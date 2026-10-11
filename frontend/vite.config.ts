import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// The API (FastAPI, `backend/src/api/`) runs on 127.0.0.1:8600; in dev Vite proxies to it. Localhost only (AGENTS rule 1).
// In the dev container (compose profile `dev`, D-053) API_URL points at the api-dev service and VITE_HOST is 0.0.0.0;
// compose still publishes the port on the host's 127.0.0.1 only.
const API = process.env.API_URL ?? "http://127.0.0.1:8600";
const HOST = process.env.VITE_HOST ?? "127.0.0.1";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { host: HOST, port: 5173, proxy: { "/api": API, "/models": API } },
  preview: { host: HOST, port: 4173, proxy: { "/api": API, "/models": API } },
  build: { outDir: "dist", chunkSizeWarningLimit: 2000 },
});
