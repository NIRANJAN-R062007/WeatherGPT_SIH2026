import type { WarningColour } from './api';

// Static class strings: Tailwind's scanner can't see template-built names.
// Shared by AskAnswer.tsx (the /ask warnings branch) and AlertsPage.tsx
// (the standalone /warnings route) — same IMD colour tokens, one place to
// change them instead of two copies drifting apart.
export const COLOUR_BAR: Record<WarningColour, string> = {
  green: 'bg-imd-green',
  yellow: 'bg-imd-yellow',
  orange: 'bg-imd-orange',
  red: 'bg-imd-red',
};

export const COLOUR_TEXT: Record<WarningColour, string> = {
  green: 'text-imd-green',
  yellow: 'text-imd-yellow',
  orange: 'text-imd-orange',
  red: 'text-imd-red',
};

export function istTimestamp(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d)} IST`;
}
