/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_SUPABASE_URL: string
  readonly VITE_SUPABASE_ANON_KEY: string
  readonly VITE_ENABLE_RFQ?: string
  readonly VITE_PERF_DEBUG?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
