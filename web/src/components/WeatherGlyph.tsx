// The mockups' coloured weather glyphs (a yellow sun peeking over a blue
// cloud, a cloud with rain…), composed from Material Symbols so they stay
// crisp at any size (mobile weather_glyph.dart). Keyed on the canonical
// condition from data/decoders/weather_conditions.json.
import { useUiPrefs } from '../state/UiPrefsContext';
import { SUN } from '../theme/personaTheme';
import { Icon } from './ui';

type Kind = 'sun' | 'moon' | 'partly' | 'partlyNight' | 'cloud' | 'rain' | 'storm' | 'wind';

function kindOf(condition: string | null | undefined, night: boolean): Kind {
  switch (condition) {
    case 'clear':
    case 'mostly_clear':
      return night ? 'moon' : 'sun';
    case 'partly_cloudy':
      return night ? 'partlyNight' : 'partly';
    case 'light_rain':
    case 'rain_showers':
    case 'rain':
    case 'heavy_rain':
      return 'rain';
    case 'thunderstorm':
    case 'thunderstorm_with_rain':
    case 'scattered_thunderstorms':
      return 'storm';
    case 'windy':
      return 'wind';
    default:
      return 'cloud';
  }
}

export default function WeatherGlyph({
  condition,
  night = false,
  size = 40,
}: {
  condition: string | null | undefined;
  night?: boolean;
  size?: number;
}) {
  const { theme: t } = useUiPrefs();
  // Flutter's Alignment(x, y): -1..1 across the free space of the box.
  const layer = (name: string, color: string, f: number, x = 0, y = 0) => {
    const s = size * f;
    return (
      <span
        key={`${name}-${x}-${y}`}
        className="absolute leading-none"
        style={{ left: ((x + 1) / 2) * (size - s), top: ((y + 1) / 2) * (size - s) }}
      >
        <Icon name={name} fill size={s} style={{ color, display: 'block', width: s, height: s }} />
      </span>
    );
  };
  let layers;
  switch (kindOf(condition, night)) {
    case 'sun':
      layers = [layer('sunny', SUN, 0.95)];
      break;
    case 'moon':
      layers = [layer('nightlight', t.moonGlyph, 0.8)];
      break;
    case 'partly':
      layers = [layer('sunny', SUN, 0.72, -0.7, -0.75), layer('cloud', t.cloudGlyph, 0.8, 0.6, 0.7)];
      break;
    case 'partlyNight':
      layers = [layer('nightlight', t.moonGlyph, 0.6, -0.7, -0.75), layer('cloud', t.cloudGlyph, 0.8, 0.6, 0.7)];
      break;
    case 'rain':
      layers = [
        layer('cloud', t.cloudGlyph, 0.8, 0, -0.6),
        layer('water_drop', t.rainGlyph, 0.3, -0.35, 0.95),
        layer('water_drop', t.rainGlyph, 0.3, 0.35, 0.95),
      ];
      break;
    case 'storm':
      layers = [layer('cloud', t.cloudGlyph, 0.8, 0, -0.6), layer('bolt', SUN, 0.45, 0, 1)];
      break;
    case 'wind':
      layers = [layer('air', t.cloudGlyph, 0.9)];
      break;
    default:
      layers = [layer('cloud', t.cloudGlyph, 0.92)];
  }
  return (
    <span className="relative inline-block shrink-0" style={{ width: size, height: size }} aria-hidden="true">
      {layers}
    </span>
  );
}
