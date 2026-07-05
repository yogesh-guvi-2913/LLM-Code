/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// This config is a .cjs file ON PURPOSE. The runtime rootfs is READ-ONLY except
// for /app/src and /tmp. Vite loads an ESM config (.js/.mjs/.ts) by bundling it
// and writing a temporary `*.timestamp-*.mjs` NEXT TO the config in /app — which
// fails with EROFS on a read-only /app. A .cjs config is bundled and evaluated
// IN MEMORY (no temp file is ever written), and its externalized deps still
// resolve from /app/node_modules. esbuild transforms this ESM source to CJS
// during Vite's config bundling, so `import`/`export default` are fine here;
// `__dirname` is the CJS global (no import.meta).
//
// node_modules is baked read-only, so Vite's cache MUST live in /tmp — never in
// node_modules/.vite (the default).
//
// Env vars this config reads:
//   HMR_CLIENT_PORT — public port the browser connects to for HMR through the
//                     orchestrator's reverse proxy (default 8090).
//   APP_SRC         — absolute path to the candidate source (default <dir>/src).
//   HARNESS_DIR     — absolute path to the scoring harness (default <dir>/harness).
const HMR_CLIENT_PORT = Number(process.env.HMR_CLIENT_PORT || 8090);
const APP_SRC = process.env.APP_SRC || path.resolve(__dirname, 'src');
const HARNESS_DIR = process.env.HARNESS_DIR || path.resolve(__dirname, 'harness');

export default defineConfig({
  plugins: [react()],

  // Redirect Vite's cache off the read-only node_modules tree.
  cacheDir: '/tmp/.vite',

  resolve: {
    alias: {
      // The harness lives outside /app and imports the candidate's component as
      // `@app/App`; this keeps that import stable regardless of harness location.
      '@app': APP_SRC,
    },
  },

  // Keep dep optimisation deterministic and pointed at the writable cache dir.
  optimizeDeps: {
    include: ['react', 'react-dom', 'react/jsx-runtime'],
  },

  server: {
    host: true,            // bind 0.0.0.0 so the orchestrator can proxy port 3000
    port: 3000,
    strictPort: true,      // fail loudly rather than drift to another port
    allowedHosts: true,    // accept proxied Host headers like sess_x.preview.localhost
    hmr: {
      // host intentionally unset — the browser reaches HMR via the reverse proxy.
      clientPort: HMR_CLIENT_PORT,
    },
  },

  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: [path.join(HARNESS_DIR, 'vitest.setup.ts')],
    // Allow vitest to load test files that live outside /app (i.e. in /harness).
    server: { deps: { inline: [/@testing-library/] } },
  },
});
