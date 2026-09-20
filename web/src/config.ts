// The only place VITE_API_BASE is read.
export const apiBase = (import.meta.env.VITE_API_BASE ?? 'http://localhost:8001').replace(
  /\/$/,
  '',
);
