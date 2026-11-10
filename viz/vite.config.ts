import { resolve } from 'node:path';
import { defineConfig } from 'vite';

// Three pages: the menu (index.html), the viewer (view.html) and the scenario generator
// (create.html). Run lists, journals, live runs and drafts come from `conflict-server`
// (src/conflict_sim/server.py); in development vite forwards to it.
const api = 'http://127.0.0.1:8780';

export default defineConfig({
  server: { proxy: { '/api': api, '/runs': api } },
  build: {
    rollupOptions: {
      input: { index: resolve(__dirname, 'index.html'), view: resolve(__dirname, 'view.html'),
        create: resolve(__dirname, 'create.html') },
    },
  },
});
