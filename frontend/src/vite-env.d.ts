/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** « false » pour appeler le Tribunal en direct ; démonstration par défaut. */
  readonly VITE_USE_MOCKS?: string;
  /** Function URL de la Lambda du Tribunal, sans « / » final. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
