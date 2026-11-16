/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** « false » : mode direct par défaut ; sinon démonstration. `?mode=` et l'interrupteur le changent (#137). */
  readonly VITE_USE_MOCKS?: string;
  /** Function URL de la Lambda du Tribunal, sans « / » final. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
