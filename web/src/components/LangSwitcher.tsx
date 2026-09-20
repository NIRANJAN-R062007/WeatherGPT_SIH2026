import type { Lang } from '../api/types';
import { LANGUAGES } from '../i18n/strings';

interface Props {
  value: Lang;
  onChange: (lang: Lang) => void;
  className?: string;
}

export function LangSwitcher({ value, onChange, className = '' }: Props) {
  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        className="h-4 w-4 text-ink-faint"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
      </svg>
      <label htmlFor="lang-switcher" className="sr-only">
        Language
      </label>
      <select
        id="lang-switcher"
        aria-label="Language"
        value={value}
        onChange={(e) => onChange(e.target.value as Lang)}
        className="rounded-sm border border-line bg-paper-hi px-2 py-1 text-sm text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-monsoon"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code} lang={l.code}>
            {l.native}
          </option>
        ))}
      </select>
    </div>
  );
}
