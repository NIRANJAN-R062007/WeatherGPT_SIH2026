import type { WarningColour } from '../api/types';

const RAIL_COLOURS: Record<WarningColour, string> = {
  green: 'bg-imd-green',
  yellow: 'bg-imd-yellow',
  orange: 'bg-imd-orange',
  red: 'bg-imd-red',
};

interface Props {
  colour: WarningColour | null;
}

/**
 * The one memorable detail: a 4px strip along the top edge carrying the
 * current warning colour for the reader's default city, on every page.
 */
export function SignalRail({ colour }: Props) {
  const className = colour ? RAIL_COLOURS[colour] : 'bg-line';
  return <div aria-hidden className={`fixed inset-x-0 top-0 z-50 h-1 ${className}`} />;
}
