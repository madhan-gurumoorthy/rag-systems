import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Vite build for the local test console.
 *
 * - `/a2a` and `/healthz` are proxied to the FastAPI backend (default
 *   port 8000) in dev so `npm run dev` is fully self-contained — open
 *   http://localhost:5174 and the SPA talks to the local backend
 *   through the proxy.
 * - Build output lands in `../static/dist/`, which `router.py` mounts
 *   at `/console`.
 * - `base` is mode-dependent: production mount at `/console` resolves
 *   assets as `/console/assets/...`; `vite dev` at :5174 uses `/`.
 */
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/console/" : "/",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5174,
    proxy: {
      "/a2a": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
        // SSE: do not buffer.
        ws: false,
      },
      "/healthz": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    sourcemap: true,
    target: "es2022",
  },
}));
