import type { Lang } from '../api/types';

const LOCALES: Record<Lang, string> = {
  en: 'en-IN',
  ta: 'ta-IN',
  hi: 'hi-IN',
  te: 'te-IN',
  mr: 'mr-IN',
};

export function localeFor(lang: Lang): string {
  return LOCALES[lang];
}

export function formatTime(iso: string, tz: string, lang: Lang): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(localeFor(lang), {
    timeZone: tz,
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    numberingSystem: 'latn',
  }).format(date);
}

export function formatDateRange(from: string, to: string, tz: string, lang: Lang): string {
  const start = new Date(from);
  const end = new Date(to);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return `${from} – ${to}`;
  const fmt = new Intl.DateTimeFormat(localeFor(lang), {
    timeZone: tz,
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    numberingSystem: 'latn',
  });
  return fmt.formatRange(start, end);
}

export function formatNumber(n: number, lang: Lang): string {
  return new Intl.NumberFormat(localeFor(lang), { numberingSystem: 'latn' }).format(n);
}
