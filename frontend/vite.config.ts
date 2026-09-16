import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

declare const process: { env: Record<string, string | undefined>; cwd?: () => string };

export default defineConfig(({ mode }) => {
  const env = typeof process !== 'undefined' && process.env ? process.env : loadEnv(mode, '.', '');
  return {
    plugins: [react()],
    server: {
      host: env.VITE_HOST || '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_BACKEND_URL || 'http://127.0.0.1:4000',
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
  };
});
