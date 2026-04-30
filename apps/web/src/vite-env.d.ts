/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_APP_ENV?: "local" | "staging" | "production";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
