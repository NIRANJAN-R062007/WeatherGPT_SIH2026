import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Opt-in dev proxy: a deployed orchestrator only allows its own origins
  // (CORS), so to develop against it set API_PROXY_TARGET to its URL and
  // VITE_API_BASE_URL=/api (e.g. in .env.local); /api/* is then forwarded
  // same-origin. Unset = no proxy, the app calls VITE_API_BASE_URL directly.
  const target = loadEnv(mode, process.cwd(), '').API_PROXY_TARGET
  const proxy = target
    ? { '/api': { target, changeOrigin: true, rewrite: (p: string) => p.replace(/^\/api/, '') } }
    : undefined
  return {
    plugins: [react()],
    server: { port: 5181, proxy },
    preview: { port: 5181, proxy },
  }
})
