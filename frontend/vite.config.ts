import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: frontend calls /api/* which Vite forwards to FastAPI,
// so no CORS or absolute-URL juggling is needed in the browser.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
});
