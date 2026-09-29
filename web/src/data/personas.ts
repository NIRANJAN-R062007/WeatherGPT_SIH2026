// The five personas — ids are services/orchestrator/persona.py's PERSONAS,
// copy is mobile/lib/state/ui_prefs.dart's kPersonas (the pics/ persona
// mockups). The persona only reframes /ask's narration and picks the
// app-wide theme (src/theme/personaTheme.ts); the facts never change.
// Icons are Material Symbols names.

/** One of a persona card's four focus chips. */
export interface PersonaFeature {
  icon: string;
  label: string;
}

/** A persona-flavoured question for Home's Quick Actions or Chat's
 *  Suggested Questions. `{city}` is replaced with the selected city. Each is
 *  something /ask's NLU answers (current weather, forecast, rain, rain so
 *  far, warnings) — the persona reframes the answer, never the facts. */
export interface PersonaQuestion {
  icon: string;
  template: string;
  /** Shorter text for Home's rows; the question itself when absent. */
  label?: string;
}

export const question = (q: PersonaQuestion, city: string) => q.template.replaceAll('{city}', city);
export const questionTitle = (q: PersonaQuestion, city: string) =>
  (q.label ?? q.template).replaceAll('{city}', city);

export interface Persona {
  id: string;
  label: string;
  icon: string;
  /** One line under the name — Settings' profile card and the persona list. */
  tagline: string;
  /** What the framing does; persona.py's hint, paraphrased. */
  blurb: string;
  /** How Home greets this persona: "Good morning, Farmer!". */
  role: string;
  /** The per-page lead lines. */
  homeLead: string;
  chatLead: string;
  askHint: string;
  forecastLead: string;
  alertsLead: string;
  /** What persona.py's hint actually frames — nothing it is told never to
   *  mention (soil, crops, sea state, visibility, runway data, safety
   *  verdicts), so a chip never promises data the answers can't carry. */
  features: PersonaFeature[];
  quickActions: PersonaQuestion[];
  suggestions: PersonaQuestion[];
}

export const PERSONAS: Persona[] = [
  {
    id: 'general',
    label: 'General Citizen',
    icon: 'person',
    tagline: 'Daily weather, lifestyle & city planning.',
    blurb: 'Plain-language current conditions and forecast.',
    role: 'Citizen',
    homeLead: "Here's the latest weather and updates for your day.",
    chatLead:
      'Get accurate weather insights and updates for your daily life — every number checked against the source data.',
    askHint: 'Ask a question about the weather…',
    forecastLead: 'Plan your day with accurate weather updates.',
    alertsLead: 'Stay informed and stay safe.',
    features: [
      { icon: 'sunny', label: 'Daily Forecast' },
      { icon: 'umbrella', label: 'Rain Chance' },
      { icon: 'air', label: 'Wind Updates' },
      { icon: 'warning', label: 'IMD Warnings' },
    ],
    quickActions: [
      { icon: 'umbrella', template: 'Will it rain today in {city}?', label: 'Will it rain today?' },
      {
        icon: 'nights_stay',
        template: 'What is the weather tonight in {city}?',
        label: 'What should I expect this evening?',
      },
      { icon: 'calendar_month', template: '5-day forecast for {city}', label: '5-day forecast' },
    ],
    suggestions: [
      { icon: 'umbrella', template: 'Will it rain tomorrow in {city}?' },
      { icon: 'calendar_month', template: '5-day forecast for {city}' },
      { icon: 'water_drop', template: 'How much rain so far today in {city}?' },
      { icon: 'warning', template: 'Any weather warnings for {city}?' },
    ],
  },
  {
    id: 'farmer',
    label: 'Farmer',
    icon: 'eco',
    tagline: 'Agriculture, crops & weather planning.',
    blurb: 'Whether conditions suit field work like spraying or harvest.',
    role: 'Farmer',
    homeLead: "Here's the latest weather for your fields.",
    chatLead:
      'Get accurate weather insights for your farming activities, backed by real-time data and trusted sources.',
    askHint: 'Ask a question about your fields…',
    forecastLead: 'Plan your farming activities with confidence.',
    alertsLead: 'Stay informed and protect your crops.',
    features: [
      { icon: 'water_drop', label: 'Rainfall Forecast' },
      { icon: 'eco', label: 'Spraying Window' },
      { icon: 'agriculture', label: 'Harvest Timing' },
      { icon: 'sunny', label: 'Heat & UV' },
    ],
    quickActions: [
      { icon: 'umbrella', template: 'Will it rain today in {city}?', label: 'Will it rain on my fields today?' },
      {
        icon: 'water_drop',
        template: 'How much rain so far today in {city}?',
        label: 'How much rain has fallen today?',
      },
      { icon: 'calendar_month', template: '5-day forecast for {city}', label: '5-day farm forecast' },
    ],
    suggestions: [
      { icon: 'eco', template: 'Will it rain tomorrow in {city}?' },
      { icon: 'eco', template: 'How much rain so far today in {city}?' },
      { icon: 'eco', template: 'How hot will it be tomorrow in {city}?' },
      { icon: 'eco', template: '5-day forecast for {city}' },
    ],
  },
  {
    id: 'fisherman',
    label: 'Fisherman',
    icon: 'sailing',
    tagline: 'Fishing, marine & coastal weather planning.',
    blurb: 'Wind and rain framed around going out to sea.',
    role: 'Fisherman',
    homeLead: "Here's the latest weather for your sea operations.",
    chatLead: 'Get accurate weather insights with real-time data and evidence for your trips out to sea.',
    askHint: 'Ask a question about the sea weather…',
    forecastLead: 'Plan your fishing trips with confidence.',
    alertsLead: 'Stay informed and stay safe at sea.',
    features: [
      { icon: 'air', label: 'Wind Conditions' },
      { icon: 'grain', label: 'Rain Chance' },
      { icon: 'calendar_month', label: 'Calmest Day' },
      { icon: 'warning', label: 'IMD Warnings' },
    ],
    quickActions: [
      { icon: 'air', template: 'What are the winds like now in {city}?', label: 'How windy is it right now?' },
      { icon: 'umbrella', template: 'Will it rain tomorrow in {city}?', label: 'Will it rain tomorrow?' },
      { icon: 'calendar_month', template: '5-day forecast for {city}', label: '5-day forecast' },
    ],
    suggestions: [
      { icon: 'waves', template: 'Will it rain tomorrow in {city}?' },
      { icon: 'waves', template: 'How strong will the winds be tomorrow in {city}?' },
      { icon: 'waves', template: 'Any weather warnings for {city}?' },
      { icon: 'waves', template: '5-day forecast for {city}' },
    ],
  },
  {
    id: 'aviation',
    label: 'Aviation',
    icon: 'flight',
    tagline: 'Flight operations and aviation weather.',
    blurb: 'Wind and visibility-relevant briefing language.',
    role: 'Pilot',
    homeLead: "Here's the latest weather for your flight operations.",
    chatLead: 'Get accurate weather insights with real-time data and evidence for your flight planning.',
    askHint: 'Ask a question about the weather…',
    forecastLead: 'Plan your flight with confidence.',
    alertsLead: 'Stay informed and fly safe.',
    features: [
      { icon: 'air', label: 'Wind & Direction' },
      { icon: 'foggy', label: 'Fog & Haze' },
      { icon: 'thunderstorm', label: 'Storm Watch' },
      { icon: 'flight_takeoff', label: 'Ops Impacts' },
    ],
    quickActions: [
      { icon: 'air', template: 'What are the winds like now in {city}?', label: 'Current wind conditions' },
      {
        icon: 'thunderstorm',
        template: 'Will it rain this evening in {city}?',
        label: 'Any rain for evening departures?',
      },
      { icon: 'calendar_month', template: '5-day forecast for {city}', label: '5-day forecast' },
    ],
    suggestions: [
      { icon: 'flight', template: 'Will it rain tomorrow in {city}?' },
      { icon: 'flight', template: 'What are the winds like now in {city}?' },
      { icon: 'flight', template: 'Any weather warnings for {city}?' },
      { icon: 'flight', template: '5-day forecast for {city}' },
    ],
  },
  {
    id: 'city_official',
    label: 'City Official',
    icon: 'account_balance',
    tagline: 'Safer cities, stronger communities.',
    blurb: 'Direct, operational public-safety framing.',
    role: 'Officer',
    homeLead: "Here's the latest weather and city updates for your operations.",
    chatLead:
      'Get accurate weather insights and city-level forecasts, backed by real-time data and official sources.',
    askHint: "Ask a question about the city's weather…",
    forecastLead: 'Plan your city operations with confidence.',
    alertsLead: 'Stay informed and keep the city safe.',
    features: [
      { icon: 'flood', label: 'Waterlogging' },
      { icon: 'thermostat', label: 'Heat Exposure' },
      { icon: 'air', label: 'Wind Hazards' },
      { icon: 'groups', label: 'Operational Outlook' },
    ],
    quickActions: [
      {
        icon: 'location_city',
        template: 'What is the weather now in {city}?',
        label: 'Check weather impact on the city',
      },
      {
        icon: 'warning',
        template: 'Any weather warnings for {city}?',
        label: 'View active alerts & advisories',
      },
      { icon: 'water_drop', template: 'How much rain so far today in {city}?', label: 'Rainfall so far today' },
    ],
    suggestions: [
      { icon: 'settings_suggest', template: 'Any weather warnings for {city}?' },
      { icon: 'settings_suggest', template: 'How much rain so far today in {city}?' },
      { icon: 'settings_suggest', template: 'How hot will it be tomorrow in {city}?' },
      { icon: 'settings_suggest', template: '5-day forecast for {city}' },
    ],
  },
];

export function personaById(id: string): Persona {
  return PERSONAS.find((p) => p.id === id) ?? PERSONAS[0];
}
