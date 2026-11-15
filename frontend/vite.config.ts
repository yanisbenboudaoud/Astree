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
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
});
