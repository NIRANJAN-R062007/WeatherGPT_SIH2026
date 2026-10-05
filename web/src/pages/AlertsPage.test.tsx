// Phase 7 B2: while fixtures are the only warnings source, the featured card
// on the Alerts page must show the "Simulated data" label for every verdict,
// active or clear. The body is the one GET /warnings returns for the fixture.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { WarningsVerdict } from '../lib/warnings';
import { UiPrefsProvider } from '../state/UiPrefsContext';
import { Verdict } from './AlertsPage';

const SIMULATED_LABEL = 'Simulated data — pending official feed access';

const legend = ['green', 'yellow', 'orange', 'red'].map((colour) => ({ colour, label: colour, meaning: `${colour} meaning` }));
const warning = {
  city: 'chennai',
  district: 'Chennai',
  colour: 'orange',
  colour_label: 'Orange',
  category: 'Heavy rainfall',
  category_label: 'Heavy rainfall',
  headline: 'Orange alert: heavy rainfall expected',
  advice: 'Avoid low-lying and waterlogging-prone areas; keep essential travel to a minimum.',
  valid_from: '2026-09-14T06:00:00+05:30',
  valid_to: '2026-09-15T06:00:00+05:30',
  issued_by: 'IMD (fixture)',
  source: 'fixture',
  disclaimer: SIMULATED_LABEL,
};
const active = { city: 'chennai', city_name: 'Chennai', status: 'active', warning, legend } as unknown as WarningsVerdict;
const clear = {
  ...active,
  status: 'clear',
  warning: { ...warning, colour: 'green', colour_label: 'Green', category: null, headline: 'No warning in force' },
} as unknown as WarningsVerdict;

function render(data: WarningsVerdict, expanded: boolean) {
  return renderToStaticMarkup(
    <UiPrefsProvider>
      <Verdict data={data} glossary={null} expanded={expanded} onToggle={() => {}} />
    </UiPrefsProvider>,
  );
}

describe('the Alerts page verdict card carries the simulated-data label', () => {
  for (const [name, data] of [['active', active], ['clear', clear]] as const) {
    for (const expanded of [false, true]) {
      it(`${name} verdict, details ${expanded ? 'open' : 'closed'}`, () => {
        expect(render(data, expanded)).toContain(SIMULATED_LABEL);
      });
    }
  }
});
