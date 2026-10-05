// AskAnswer renders every shape the `warnings` intent can come back in. Since the
// 3 Oct location change that includes replies with no demo city, no `status` and
// no `legend`, which used to throw while rendering and blank the answer panel.
// Rendered to static markup (no DOM needed); the bodies are the ones
// services/orchestrator/main.py builds.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { classifyAsk, type AskResponse } from '../lib/api';
import { UiPrefsProvider } from '../state/UiPrefsContext';
import AskAnswer from './AskAnswer';

const nlu = {
  intent: 'warnings',
  city: null,
  time_window: 'today',
  days: null,
  parameter: 'general',
  language: 'en',
  source: 'rules',
  confidence: 0.9,
};
const legend = ['green', 'yellow', 'orange', 'red'].map((colour) => ({
  colour,
  label: `${colour} label`,
  meaning: `${colour} meaning`,
}));
const trichy = { label: 'Tiruchirappalli, Tamil Nadu', source: 'gazetteer', lat: 10.82, lon: 78.7, place_id: 'gn:1254388' };
const unavailable = 'Weather warnings are not available right now.';

function render(body: object, props: { detail?: boolean; onPickPlace?: () => void; onUseLocation?: () => void } = {}) {
  const outcome = classifyAsk({ intent: 'warnings', nlu, ...body } as unknown as AskResponse);
  return renderToStaticMarkup(
    <UiPrefsProvider>
      <AskAnswer asked="red alert in Trichy?" loading={false} outcome={outcome} error={null} {...props} />
    </UiPrefsProvider>,
  );
}

describe('the warnings-unavailable panel', () => {
  it('names a place that is not a demo city by its location label (city is null)', () => {
    const html = render({ city: null, location: trichy, message: unavailable, status: 'unavailable', warning: null, legend });
    expect(html).toContain('No warning verdict');
    expect(html).toContain('Tiruchirappalli, Tamil Nadu');
    expect(html).toContain('UNAVAILABLE');
    expect(html).toContain(unavailable);
  });

  it('still names a demo city', () => {
    const html = render({ city: 'chennai', message: unavailable, status: 'unavailable', warning: null, legend });
    expect(html).toContain('Chennai');
  });

  it('renders without a status, a legend or a place, even with the detail on', () => {
    const html = render({ message: unavailable }, { detail: true });
    expect(html).toContain('No warning verdict');
    expect(html).toContain('UNAVAILABLE'); // a missing status reads as unavailable, never as a verdict
    expect(html).toContain(unavailable);
    expect(html).not.toContain('green label');
  });

  it('shows the colour legend when the detail is on and the reply has one', () => {
    const html = render({ city: null, location: trichy, message: unavailable, status: 'unavailable', legend }, { detail: true });
    expect(html).toContain('green label');
    expect(html).toContain('red meaning');
  });
});

describe('a warnings location reply is a fallback panel with the places and the location button', () => {
  it('lists the places to tap when several share the name', () => {
    const candidates = [
      { place_id: 'gn:1', label: 'Aurangabad, Maharashtra', district: 'Aurangabad', state: 'Maharashtra' },
      { place_id: 'gn:2', label: 'Aurangabad, Bihar', district: 'Aurangabad', state: 'Bihar' },
    ];
    const html = render({ message: 'Which place?', ambiguous: candidates }, { onPickPlace: vi.fn() });
    expect(html).toContain('Which place?');
    expect(html.match(/data-testid="place-candidate"/g)).toHaveLength(2);
    expect(html).toContain('Aurangabad, Bihar');
    expect(html).not.toContain('No warning verdict');
  });

  it('offers the nearest place when the named one is not found', () => {
    const nearest = { place_id: 'gn:3', label: 'Auroville, Tamil Nadu', district: 'Villupuram', state: 'Tamil Nadu', lat: 12, lon: 79.8 };
    const html = render({ message: 'Not found', not_found: true, nearest }, { onPickPlace: vi.fn() });
    expect(html).toContain('Place not found');
    expect(html).toContain('Use Auroville, Tamil Nadu');
  });

  it('offers "Use my location" when no place was given', () => {
    const html = render({ message: 'Which place? Name a town or city, or share your location.', needs_location: true }, { onUseLocation: vi.fn() });
    expect(html).toContain('Use my location');
    expect(html).toContain('Name a town or city');
    expect(html).not.toContain('No warning verdict');
  });

  it('shows the India-only and offline replies as plain messages', () => {
    const india = render({ message: 'Only places in India.', outside_india: true });
    expect(india).toContain('Only places in India.');
    expect(india).not.toContain('No warning verdict');
    const offline = render({ message: 'Offline, I only have saved data for Chennai.', offline: true, location: trichy });
    expect(offline).toContain('Offline, I only have saved data for Chennai.');
    expect(offline).not.toContain('No warning verdict');
  });
});
