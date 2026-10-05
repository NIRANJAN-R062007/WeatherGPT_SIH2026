// classifyAsk sorts a raw /ask body into the branch AskAnswer renders. The bodies
// below are the shapes services/orchestrator/main.py builds for the `warnings`
// intent (checked with FastAPI's TestClient in fixtures and auto mode), plus one
// of each other branch so the sort stays what it was.
import { describe, expect, it } from 'vitest';
import { classifyAsk, type AskResponse } from './api';

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
const legend = ['green', 'yellow', 'orange', 'red'].map((colour) => ({ colour, label: colour, meaning: colour }));
const trichy = { label: 'Tiruchirappalli, Tamil Nadu', source: 'gazetteer', lat: 10.82, lon: 78.7, place_id: 'gn:1254388' };
const candidate = { place_id: 'gn:1278149', label: 'Aurangabad, Maharashtra', district: 'Aurangabad', state: 'Maharashtra' };

const classify = (body: object) => classifyAsk({ intent: 'warnings', nlu, ...body } as unknown as AskResponse).kind;

describe('classifyAsk: the warnings intent', () => {
  it('sends a verdict (response + warning) to warnings', () => {
    expect(classify({ city: 'chennai', response: 'No warning in force', status: 'clear', warning: {}, legend })).toBe(
      'warnings',
    );
  });

  it('sends a demo city with no usable feed to warnings-unavailable', () => {
    const body = { city: 'chennai', message: 'Not available', status: 'unavailable', warning: null, legend };
    expect(classify(body)).toBe('warnings-unavailable');
  });

  it('sends a resolved place that is not a demo city (city null) to warnings-unavailable', () => {
    // "red alert in Trichy?" online, and a GPS fix: the place is in `location`.
    const body = { city: null, location: trichy, message: 'Not available', status: 'unavailable', warning: null, legend };
    expect(classify(body)).toBe('warnings-unavailable');
  });

  it.each([
    ['which place?', { message: 'Which place?', ambiguous: [candidate] }],
    ['place not found', { message: 'Not found', not_found: true, nearest: { ...candidate, lat: 1, lon: 2 } }],
    ['no place given', { message: 'Which place? Name a town.', needs_location: true }],
    ['India only', { message: 'India only', outside_india: true }],
    ['offline, no saved data', { message: 'Offline', offline: true, location: trichy }],
  ])('sends the location reply "%s" to fallback, not to the verdict panel', (_name, body) => {
    expect(classify(body)).toBe('fallback');
  });
});

describe('classifyAsk: the other branches are unchanged', () => {
  const grounding = { ok: true, matched: 1, total: 1, figures: [] };
  const provenance = { source: 's', issued: null, is_live: false, retrieved_at: 'now' };

  it('keeps a success that carries offline: true a success', () => {
    const body = { intent: 'current_weather', city: 'chennai', day: 'today', response: 'x', offline: true, provenance, grounding, nlu };
    expect(classifyAsk(body as unknown as AskResponse).kind).toBe('success');
  });

  it('sorts ungrounded and fallback replies as before', () => {
    const ungrounded = { intent: 'current_weather', city: 'chennai', message: 'm', provenance, grounding, nlu };
    expect(classifyAsk(ungrounded as unknown as AskResponse).kind).toBe('ungrounded');
    const fallback = { intent: 'unrecognized', message: 'm', nlu };
    expect(classifyAsk(fallback as unknown as AskResponse).kind).toBe('fallback');
    const location = { intent: 'current_weather', message: 'Which place?', needs_location: true, nlu };
    expect(classifyAsk(location as unknown as AskResponse).kind).toBe('fallback');
  });
});
