// The redesign's recurring pieces (pics/ mockups, mobile/lib/components/
// surfaces.dart + common.dart): the bordered card, the section title, the
// tinted icon disc, the icon + text + chevron row that Quick Actions,
// Suggested Questions, alert lists and Settings rows share, banners, status
// panels and the picker sheet. Every colour is a persona token
// (tailwind.config.js), so these re-tint with the persona and appearance.
import { useEffect, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useT, type Args } from '../lib/i18n';

export function Icon({
  name,
  size = 20,
  fill = false,
  className = '',
  style,
}: {
  name: string;
  size?: number;
  fill?: boolean;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      aria-hidden="true"
      className={`material-symbols-outlined select-none ${fill ? 'icon-fill' : ''} ${className}`}
      style={{ fontSize: size, ...style }}
    >
      {name}
    </span>
  );
}

/** Card with a hairline persona-tinted border and a soft tinted lift.
 *  `wash` fades it from the card colour into the persona tint (weather
 *  cards). Clickable when given onClick. */
export function AppCard({
  children,
  className = '',
  pad = 'p-space-md',
  wash = false,
  onClick,
  style,
  label,
}: {
  children: ReactNode;
  className?: string;
  pad?: string;
  wash?: boolean;
  onClick?: () => void;
  style?: CSSProperties;
  label?: string;
}) {
  const cls = `block w-full text-left rounded-card border border-card-border shadow-card ${
    wash ? 'bg-wash' : 'bg-card'
  } ${pad} ${className}`;
  if (onClick) {
    return (
      <button
        type="button"
        aria-label={label}
        onClick={onClick}
        style={style}
        className={`${cls} transition hover:border-primary/40 hover:brightness-[0.99] active:scale-[0.995] focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary`}
      >
        {children}
      </button>
    );
  }
  return (
    <div className={cls} style={style}>
      {children}
    </div>
  );
}

/** "Quick Actions", "Active Alerts" — with an optional trailing link. */
export function SectionTitle({ text, action, onAction }: { text: string; action?: string; onAction?: () => void }) {
  const t = useT();
  return (
    <div className="flex items-center gap-2">
      <h2 className="flex-1 font-headline-sm text-headline-sm font-bold text-ink">{t(text)}</h2>
      {action && (
        <button
          type="button"
          onClick={onAction}
          className="px-1.5 py-1 rounded-lg font-label-md text-label-md font-semibold text-primary hover:bg-tint"
        >
          {t(action)}
        </button>
      )}
    </div>
  );
}

/** A round tinted disc holding one icon. `solid` discs without an explicit
 *  colour fill with the persona's accent gradient. */
export function IconDisc({
  icon,
  size = 40,
  solid = false,
  color,
  className = '',
}: {
  icon: string;
  size?: number;
  solid?: boolean;
  /** A literal CSS colour (IMD bands, muted discs) instead of the accent. */
  color?: string;
  className?: string;
}) {
  const style: CSSProperties = { width: size, height: size };
  let cls = 'bg-tint text-primary';
  if (solid && !color) cls = 'bg-accent-gradient text-on-primary';
  else if (solid && color) {
    cls = 'text-white';
    style.background = color;
  } else if (color) {
    style.color = color;
    style.background = `color-mix(in srgb, ${color} 12%, transparent)`;
    cls = '';
  }
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-full ${cls} ${className}`} style={style}>
      <Icon name={icon} size={Math.round(size * 0.52)} fill={solid} />
    </span>
  );
}

/** Icon disc, title (+ optional subtitle lines), chevron. `leading`
 *  replaces the disc when a row needs a custom glyph. */
export function ActionRow({
  icon,
  leading,
  iconColor,
  plainIcon = false,
  title,
  subtitle,
  detail,
  onClick,
  disabled = false,
  trailing,
}: {
  icon?: string;
  leading?: ReactNode;
  iconColor?: string;
  /** A bare accent glyph instead of the tinted disc (the Settings rows). */
  plainIcon?: boolean;
  title: string;
  subtitle?: string;
  detail?: string;
  onClick?: () => void;
  disabled?: boolean;
  /** Replaces the chevron; `null` shows nothing. */
  trailing?: ReactNode | null;
}) {
  const t = useT();
  const lead =
    leading ??
    (plainIcon ? (
      <span className="w-8 flex justify-center text-primary" style={iconColor ? { color: iconColor } : undefined}>
        <Icon name={icon ?? 'circle'} size={24} />
      </span>
    ) : (
      <IconDisc icon={icon ?? 'circle'} color={iconColor} />
    ));
  return (
    <div className={disabled ? 'opacity-60' : ''}>
      <AppCard pad="px-3 py-2.5" onClick={disabled ? undefined : onClick}>
        <div className="flex items-center gap-3">
          {lead}
          <div className="flex-1 min-w-0">
            <div className={`font-label-md text-label-md text-ink ${subtitle ? 'font-semibold' : 'font-medium'}`}>
              {t(title)}
            </div>
            {subtitle && <div className="font-body-sm text-body-sm text-ink-muted mt-px">{t(subtitle)}</div>}
            {detail && <div className="font-body-sm text-body-sm text-ink-muted">{t(detail)}</div>}
          </div>
          {trailing === undefined ? <Icon name="chevron_right" size={20} className="text-ink-muted" /> : trailing}
        </div>
      </AppCard>
    </div>
  );
}

/** The "i" / shield banner at the foot of Forecast and Alerts. */
export function InfoBanner({
  icon,
  title,
  body,
  onClick,
}: {
  icon: string;
  title: string;
  body?: string;
  onClick?: () => void;
}) {
  const t = useT();
  const inner = (
    <>
      <IconDisc icon={icon} solid size={32} />
      <span className="flex-1 min-w-0 text-left">
        <span className="block font-label-md text-label-md font-semibold text-ink">{t(title)}</span>
        {body && <span className="block font-body-sm text-body-sm text-ink-muted">{t(body)}</span>}
      </span>
      {onClick && <Icon name="chevron_right" size={20} className="text-primary" />}
    </>
  );
  const cls = 'w-full flex items-center gap-3 p-3.5 rounded-card bg-tint';
  return onClick ? (
    <button type="button" onClick={onClick} className={`${cls} hover:bg-tint-strong transition-colors`}>
      {inner}
    </button>
  ) : (
    <div className={cls}>{inner}</div>
  );
}

/** The page title + lead line each page's sheet opens with. */
export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  const t = useT();
  return (
    <div>
      <h1 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg font-bold text-ink">{t(title)}</h1>
      {subtitle && <p className="mt-space-xs font-body-md text-body-md text-ink-muted">{t(subtitle)}</p>}
    </div>
  );
}

/** `font-citation-mono uppercase` label with a trailing rule —
 *  "⚡ LIVE — ANSWERS COME FROM /ASK ────". */
export function RuleLabel({ icon, text }: { icon: string; text: string }) {
  const t = useT();
  return (
    <div className="flex items-center gap-2 font-citation-mono text-citation-mono text-primary uppercase tracking-wider">
      <Icon name={icon} size={14} />
      <span>{t(text)}</span>
      <span className="flex-1 h-px bg-outline-variant/50" />
    </div>
  );
}

/** AskAnswer.tsx's chip: `px-2 py-0.5 rounded-full font-citation-mono text-[10px]`. */
export function TagChip({ children, icon, tone = 'neutral' }: { children: ReactNode; icon?: string; tone?: 'neutral' | 'primary' }) {
  const t = useT();
  return (
    <span
      className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full font-citation-mono text-[10px] font-medium ${
        tone === 'primary' ? 'bg-surface-container-high text-primary' : 'bg-surface-container text-on-surface-variant'
      }`}
    >
      {icon && <Icon name={icon} size={11} />}
      {typeof children === 'string' ? t(children) : children}
    </span>
  );
}

/** The LIVE / NOT LIVE provenance badge; `notLiveText` replaces NOT LIVE
 *  (SAVED, for a saved copy). */
export function LiveBadge({ live, notLiveText = 'NOT LIVE' }: { live: boolean; notLiveText?: string }) {
  const t = useT();
  return (
    <span
      className={`px-1.5 py-0.5 rounded font-citation-mono text-citation-mono font-semibold ${
        live ? 'bg-secondary-container text-on-secondary-container' : 'bg-surface-container-high text-on-surface-variant'
      }`}
    >
      {t(live ? 'LIVE' : notLiveText)}
    </span>
  );
}

export function Spinner({ className = 'w-4 h-4 border-outline-variant border-t-primary' }: { className?: string }) {
  return <span className={`inline-block shrink-0 rounded-full border-2 animate-spin ${className}`} />;
}

/** `p-space-md rounded-xl bg-surface-container-low` loading line. */
export function LoadingPanel({ text }: { text: string }) {
  const t = useT();
  return (
    <div className="flex items-center gap-2 p-space-md rounded-xl bg-surface-container-low font-body-md text-body-md text-on-surface-variant">
      <Spinner />
      {t(text)}
    </div>
  );
}

/** `bg-error-container text-on-error-container` failure panel. */
export function ErrorPanel({
  icon,
  title,
  message,
  messageArgs,
  onRetry,
}: {
  icon: string;
  title: string;
  message: string;
  /** Values for `message`'s `{name}` placeholders. */
  messageArgs?: Args;
  onRetry?: () => void;
}) {
  const t = useT();
  return (
    <div className="flex flex-col gap-1 p-space-md rounded-xl bg-error-container text-on-error-container">
      <div className="flex items-center gap-1.5 font-label-md text-label-md font-semibold">
        <Icon name={icon} size={18} />
        {t(title)}
      </div>
      <p className="font-body-md text-body-md">{t(message, messageArgs)}</p>
      {onRetry && (
        <div className="mt-space-sm">
          <PillButton icon="refresh" label="Try again" onClick={onRetry} />
        </div>
      )}
    </div>
  );
}

/** Shown while a page is on saved replies (lib/responseCache.ts): `message`
 *  says what couldn't be reached and when the copy was saved; neutral, like
 *  a "no verdict" card, never an error colour or a green. */
export function SavedDataBanner({
  message,
  messageArgs,
  onRetry,
}: {
  message: string;
  messageArgs?: Args;
  onRetry?: () => void;
}) {
  const t = useT();
  return (
    <div role="status" className="flex flex-col gap-1 p-space-md rounded-xl border border-outline-variant bg-surface-container-low">
      <div className="flex items-center gap-1.5 font-label-md text-label-md font-semibold text-ink">
        <Icon name="cloud_off" size={18} className="text-on-surface-variant" />
        {t('Showing saved data')}
      </div>
      <p className="font-body-md text-body-md text-on-surface-variant">{t(message, messageArgs)}</p>
      {onRetry && (
        <div className="mt-space-sm">
          <PillButton icon="refresh" label="Try again" onClick={onRetry} />
        </div>
      )}
    </div>
  );
}

/** `rounded-lg bg-primary-fixed text-on-primary-fixed` small action. */
export function PillButton({ icon, label, onClick }: { icon: string; label: string; onClick?: () => void }) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-fixed text-on-primary-fixed font-label-md text-label-md hover:brightness-95"
    >
      <Icon name={icon} size={18} />
      {t(label)}
    </button>
  );
}

/** A picker: a bottom sheet on phones, a centred dialog on wider screens
 *  (mobile's showModalBottomSheet). Esc or a backdrop click closes it. */
export function Sheet({
  open,
  onClose,
  title,
  note,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  note?: string;
  children: ReactNode;
}) {
  const t = useT();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center" role="presentation">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t(title)}
        className="relative w-full sm:max-w-md max-h-[85vh] overflow-y-auto bg-sheet rounded-t-2xl sm:rounded-2xl shadow-xl px-space-md pt-3 pb-space-md pb-safe"
      >
        <div className="mx-auto mb-3 h-1 w-8 rounded-full bg-outline-variant sm:hidden" />
        <div className="flex items-start gap-2 mb-space-md">
          <div className="flex-1">
            <h2 className="font-headline-sm text-headline-sm text-ink">{t(title)}</h2>
            {note && <p className="font-body-sm text-body-sm text-ink-muted mt-0.5">{t(note)}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('Close')}
            className="p-1 -mr-1 rounded-full text-ink-muted hover:bg-tint"
          >
            <Icon name="close" size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

/** One choice in a Sheet picker. */
export function OptionTile({
  label,
  detail,
  selected,
  onClick,
}: {
  label: string;
  detail?: string;
  selected: boolean;
  onClick: () => void;
}) {
  const t = useT();
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={`w-full flex items-center gap-2 px-space-md py-3 rounded-xl border text-left transition-colors ${
        selected ? 'bg-tint border-primary' : 'bg-card border-card-border hover:bg-tint'
      }`}
    >
      <span className={`flex-1 font-label-md text-label-md text-ink ${selected ? 'font-bold' : 'font-medium'}`}>
        {t(label)}
      </span>
      {detail && <span className="font-body-sm text-body-sm text-ink-muted">{t(detail)}</span>}
      {selected && <Icon name="check_circle" size={20} fill className="text-primary" />}
    </button>
  );
}
