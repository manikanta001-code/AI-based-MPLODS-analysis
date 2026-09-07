import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api and /auth to the FastAPI backend (Phase 3), so the
// frontend can call relative paths like fetch("/api/works") in both dev and
// prod without hardcoding a host — see src/api/client.js.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
    },
  },
});
