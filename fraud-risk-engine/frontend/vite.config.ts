import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // neko chromium container reaches vite via http://host.docker.internal:5173;
    // Vite 5+ rejects unknown Host headers by default, so allow the Docker bridge name.
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://localhost:8888",
        changeOrigin: true,
        // Don't follow redirects — pass through as-is
        secure: false,
      },
    },
  },
});
