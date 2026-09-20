interface Props {
  items: (string | undefined)[];
  badge?: { label: string; fixture?: boolean };
  className?: string;
}

/** Mono meta line, e.g. `CHENNAI · 04:23 IST · GOOGLE WEATHER · LIVE`. */
export function MetaLine({ items, badge, className = '' }: Props) {
  const parts = items.filter((item): item is string => Boolean(item));
  return (
    <div
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs uppercase tracking-[0.18em] text-ink-faint ${className}`}
    >
      {parts.map((part, i) => (
        <span key={i} className="flex items-center gap-2 whitespace-nowrap">
          {i > 0 && <span aria-hidden>·</span>}
          {part}
        </span>
      ))}
      {badge && (
        <span
          className={`rounded-sm px-1.5 py-0.5 text-[10px] tracking-[0.1em] ${
            badge.fixture ? 'bg-turmeric-tint text-ink' : 'bg-paper-dim text-ink-dim'
          }`}
        >
          {badge.label}
        </span>
      )}
    </div>
  );
}
