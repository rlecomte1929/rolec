import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// HR Dashboard dev server runs on 3100 to avoid clashing with frontend/'s 3000.
// /api/* is proxied to the same FastAPI backend the main frontend talks to.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    dedupe: ['react', 'react-dom', 'react-router-dom'],
  },
  server: {
    port: 3100,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'axios-vendor': ['axios'],
        },
      },
    },
  },
});
