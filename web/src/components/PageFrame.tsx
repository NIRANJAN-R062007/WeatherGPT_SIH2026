// A page (mobile scenery.dart's PageFrame): the city pill over the persona's
// painted scene, then the rounded content sheet holding the page, with a
// scenery strip pinned to the sheet's foot. Short pages still fill the
// window; `dock` sticks under the content (Chat's composer).
import type { ReactNode } from 'react';
import { CityPill } from './CityPicker';
import { PersonaScenery } from './scenery/Scenery';

/** Which scenery strip sits at the foot of the sheet: the persona's full
 *  landscape, its quieter form (swells / soft hills), or nothing. */
export type SceneryFooter = 'none' | 'landscape' | 'soft';

const SCENERY_HEADER_HEIGHT = 112;

export function SceneryHeader({ showCityPill = true }: { showCityPill?: boolean }) {
  return (
    <div className="relative shrink-0" style={{ height: SCENERY_HEADER_HEIGHT }}>
      <PersonaScenery slot="header" />
      {showCityPill && (
        <div className="absolute inset-x-0 top-1 flex justify-center">
          <CityPill />
        </div>
      )}
    </div>
  );
}

export default function PageFrame({
  children,
  footer = 'landscape',
  showCityPill = true,
  dock,
  wide = false,
}: {
  children: ReactNode;
  footer?: SceneryFooter;
  showCityPill?: boolean;
  dock?: ReactNode;
  /** Let the content use the full desktop width (Home's two columns). */
  wide?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <SceneryHeader showCityPill={showCityPill} />
      <section className="relative flex flex-1 flex-col bg-sheet rounded-t-sheet shadow-[0_-2px_16px_rgb(var(--c-shadow)/0.06)]">
        <div
          className={`relative z-10 mx-auto w-full flex-1 px-5 pt-space-lg ${wide ? 'max-w-6xl' : 'max-w-3xl'} ${
            footer === 'none' ? 'pb-space-lg' : 'pb-[88px]'
          }`}
        >
          {children}
        </div>
        {footer !== 'none' && (
          <div className="absolute inset-x-0 bottom-0 h-[72px] overflow-hidden">
            <PersonaScenery slot={footer === 'soft' ? 'soft' : 'footer'} />
          </div>
        )}
        {dock}
      </section>
    </div>
  );
}
