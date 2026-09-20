import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

type BaseProps = {
  children: ReactNode;
  className?: string;
};

type ButtonProps = BaseProps & {
  as: 'button';
  type: 'button' | 'submit';
  onClick?: () => void;
  disabled?: boolean;
};

type LinkProps = BaseProps & {
  as: 'link';
  to: string;
};

type Props = ButtonProps | LinkProps;

const BASE_CLASSES =
  'group relative inline-flex items-center justify-center overflow-hidden rounded-sm border border-ink/20 px-6 py-3 text-sm font-medium uppercase tracking-[0.12em] text-ink transition-colors duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-monsoon active:scale-[0.98]';

const FILL = (
  <span
    aria-hidden
    className="absolute inset-0 origin-bottom scale-y-0 bg-monsoon transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:scale-y-100 gpu"
  />
);

/**
 * CTA with a layered hover fill — a solid panel wipes up from the bottom
 * edge rather than the background cross-fading to a new colour. Composites
 * on the GPU via a transform.
 */
export function FillButton(props: Props) {
  const contentClasses = 'relative group-hover:text-paper-hi';

  if (props.as === 'button') {
    const { children, className = '', type, onClick, disabled } = props;
    return (
      <button
        type={type}
        onClick={onClick}
        disabled={disabled}
        className={`${BASE_CLASSES} ${disabled ? 'cursor-not-allowed opacity-50' : ''} ${className}`}
      >
        {!disabled && FILL}
        <span className={contentClasses}>{children}</span>
      </button>
    );
  }

  const { children, className = '', to } = props;
  return (
    <Link to={to} className={`${BASE_CLASSES} ${className}`}>
      {FILL}
      <span className={contentClasses}>{children}</span>
    </Link>
  );
}
