import { apiBase } from '../config';

export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <p className="text-sm text-ink-dim">
          Data: Google Weather API · Warnings: IMD (fixture until CAP feed) · Smart India
          Hackathon 2026
        </p>
        <p className="mt-2 font-mono text-xs text-ink-faint">{apiBase}</p>
      </div>
    </footer>
  );
}
