import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  css: { modules: { localsConvention: 'camelCaseOnly' } },
  // La table des paniers (src/data/generated/paniers) pèse environ 1,8 Mo : elle n'est chargée
  // qu'à l'écran Décision d'un profil en mode panier.
  build: { chunkSizeWarningLimit: 2000 },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Les tests rejouent toujours les procès enregistrés, même si .env.local active le mode direct.
    env: { VITE_USE_MOCKS: 'true', VITE_API_URL: '' },
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
});
