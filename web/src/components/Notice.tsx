import type { ReactNode } from 'react';

type Variant = 'info' | 'warn' | 'error' | 'refusal';

interface Props {
  variant: Variant;
  children: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  info: 'border-monsoon',
  warn: 'border-turmeric',
  error: 'border-imd-red',
  refusal: 'border-line-dim',
};

export function Notice({ variant, children, onRetry, retryLabel, className = '' }: Props) {
  const role = variant === 'error' ? 'alert' : 'status';
  return (
    <div
      role={role}
      className={`border-l-[3px] bg-paper-dim px-4 py-3 text-sm text-ink ${VARIANT_CLASSES[variant]} ${className}`}
    >
      <div>{children}</div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 font-mono text-xs uppercase tracking-[0.14em] text-monsoon underline underline-offset-2 hover:text-monsoon-dim focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-monsoon"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}
