// English display names, mirrored from data/cities.json (repo root) — the
// shared source of truth also consumed by services/orchestrator/cities.py
// and duplicated into prototype/frontend/WeatherGPT.dc.html's CITIES object.
// Keep in sync until this page fetches a live /cities endpoint.
export interface City {
  key: string;
  name: string;
  region: string;
}

export const CITIES: City[] = [
  { key: 'chennai', name: 'Chennai', region: 'Tamil Nadu' },
  { key: 'madurai', name: 'Madurai', region: 'Tamil Nadu' },
  { key: 'coimbatore', name: 'Coimbatore', region: 'Tamil Nadu' },
  { key: 'bengaluru', name: 'Bengaluru', region: 'Karnataka' },
  { key: 'hyderabad', name: 'Hyderabad', region: 'Telangana' },
  { key: 'mumbai', name: 'Mumbai', region: 'Maharashtra' },
  { key: 'delhi', name: 'Delhi', region: 'Delhi' },
  { key: 'thiruvananthapuram', name: 'Thiruvananthapuram', region: 'Kerala' },
];
