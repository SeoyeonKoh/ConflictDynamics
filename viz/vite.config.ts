import { resolve } from 'node:path';
import { defineConfig } from 'vite';

// Two pages: the menu (index.html) and the viewer (view.html). Run lists, journals and live runs
// come from `conflict-server` (src/conflict_sim/server.py); in development vite forwards to it.
const api = 'http://127.0.0.1:8780';

export default defineConfig({
  server: { proxy: { '/api': api, '/runs': api } },
  build: {
    rollupOptions: {
      input: { index: resolve(__dirname, 'index.html'), view: resolve(__dirname, 'view.html') },
    },
  },
});
