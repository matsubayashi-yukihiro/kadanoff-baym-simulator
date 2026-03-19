import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

function parseOptionalPort(value: string | undefined): number | undefined {
  if (!value) {
    return undefined;
  }

  const port = Number.parseInt(value, 10);
  return Number.isNaN(port) ? undefined : port;
}

const hmrClientPort = parseOptionalPort(process.env.VITE_HMR_CLIENT_PORT);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    hmr: hmrClientPort ? { clientPort: hmrClientPort } : undefined,
    watch: {
      usePolling: process.env.CHOKIDAR_USEPOLLING === "true",
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
});
