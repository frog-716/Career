import { defineConfig } from 'vite';

export default defineConfig({
  build: { rollupOptions: { input: { index: 'index.html', editor: 'editor.html' } } },
});
