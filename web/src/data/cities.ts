// English display names, mirrored from data/cities.json (repo root) — the
// shared source of truth also consumed by services/orchestrator/cities.py
// and duplicated into prototype/frontend/WeatherGPT.dc.html's CITIES object.
// Keep in sync until this page fetches a live /cities endpoint.
export interface City {
  key: string;
  name: string;
  region: string;
  lat: number;
  lon: number;
}

export const CITIES: City[] = [
  { key: 'chennai', name: 'Chennai', region: 'Tamil Nadu', lat: 13.0827, lon: 80.2707 },
  { key: 'madurai', name: 'Madurai', region: 'Tamil Nadu', lat: 9.9252, lon: 78.1198 },
  { key: 'coimbatore', name: 'Coimbatore', region: 'Tamil Nadu', lat: 11.0168, lon: 76.9558 },
  { key: 'bengaluru', name: 'Bengaluru', region: 'Karnataka', lat: 12.9716, lon: 77.5946 },
  { key: 'hyderabad', name: 'Hyderabad', region: 'Telangana', lat: 17.385, lon: 78.4867 },
  { key: 'mumbai', name: 'Mumbai', region: 'Maharashtra', lat: 19.076, lon: 72.8777 },
  { key: 'delhi', name: 'Delhi', region: 'Delhi', lat: 28.6139, lon: 77.209 },
  { key: 'thiruvananthapuram', name: 'Thiruvananthapuram', region: 'Kerala', lat: 8.5241, lon: 76.9366 },
];

/** Resolved city keys come back lowercase ("chennai"); use the English
 *  display name, and only fall back to capitalising the key for a city this
 *  bundle doesn't list yet. */
export function cityLabel(key: string) {
  const match = CITIES.find((c) => c.key === key);
  if (match) return match.name;
  return key.charAt(0).toUpperCase() + key.slice(1);
}

/** /ask and /warnings take a city, not coordinates, so "use my location"
 *  means the nearest of these registered cities (mobile cities.dart). */
export function nearestCity(lat: number, lon: number): City {
  const rad = (d: number) => (d * Math.PI) / 180;
  const km = (c: City) => {
    const dLat = rad(c.lat - lat);
    const dLon = rad(c.lon - lon);
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat)) * Math.cos(rad(c.lat)) * Math.sin(dLon / 2) ** 2;
    return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  };
  return CITIES.reduce((best, c) => (km(c) < km(best) ? c : best));
}
