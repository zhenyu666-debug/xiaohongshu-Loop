import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
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
