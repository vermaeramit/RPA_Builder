import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend so the frontend can use /api/* paths.
    // ws: true lets the WebSocket run-log stream pass through too.
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", ws: true },
    },
  },
});
