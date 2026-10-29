// A /climate body for the climate tests: shaped as climate.py's public() builds
// it, with a made-up but plausible series (1996–2026; 2026 is incomplete, as
// ERA5 lags and the year isn't over, so its figures are null).
import type { ClimateResponse, ClimateTrend } from '../lib/climate';

export const LABEL = 'Open-Meteo / ERA5 reanalysis, not IMD station data';

export function trend(over: Partial<ClimateTrend> = {}): ClimateTrend {
  return {
    status: 'ok',
    n: 30,
    first_year: 1996,
    last_year: 2025,
    mean: 1034.83,
    slope_per_decade: 84.021,
    stderr_per_decade: 54.606,
    significant_95: false,
    ...over,
  };
}

export function climateBody(
  over: Partial<ClimateResponse> & { missingYears?: number[]; yearRain?: ClimateTrend; yearTemp?: ClimateTrend } = {},
): ClimateResponse {
  const { missingYears = [2026], yearRain, yearTemp, ...rest } = over;
  const annual = [];
  const seasonal = [];
  for (let y = 1996; y <= 2026; y++) {
    const miss = missingYears.includes(y);
    annual.push({
      year: y,
      rain_mm: miss ? null : 900 + (y - 1996) * 5 + (y % 3) * 40,
      temp_mean_c: miss ? null : 28 + (y - 1996) * 0.02,
    });
    seasonal.push({ year: y, season: 'monsoon', rain_mm: miss ? null : 300 + (y - 1996) * 2, temp_mean_c: miss ? null : 31 });
    seasonal.push({ year: y, season: 'winter', rain_mm: 25, temp_mean_c: 25.5 });
  }
  return {
    status: 'ok',
    city: 'chennai',
    is_live: true,
    retrieved_at: '2026-10-29T12:51:12+00:00',
    requested: { start_date: '1996-01-01', end_date: '2026-10-22' },
    annual,
    seasonal,
    trends: {
      year: {
        rain_mm: yearRain ?? trend(),
        temp_mean_c: yearTemp ?? trend({ mean: 28.2, slope_per_decade: 0.243, stderr_per_decade: 0.041, significant_95: true }),
      },
      season: {
        monsoon: {
          rain_mm: trend({ mean: 330, slope_per_decade: 20, stderr_per_decade: 4, significant_95: true }),
          temp_mean_c: trend({ status: 'insufficient_data', n: 4, mean: null, slope_per_decade: null, stderr_per_decade: null }),
        },
      },
    },
    label: LABEL,
    credit: { text: 'Weather data by Open-Meteo.com', url: 'https://open-meteo.com/' },
    changes_note: "Monthly, seasonal and annual figures and trends are computed by WeatherGPT from Open-Meteo's daily ERA5 values.",
    calendar_note: "Months and seasons are fixed calendar windows. They are not IMD's declared monsoon onset or withdrawal.",
    licence_url: 'https://open-meteo.com/en/licence',
    terms_url: 'https://open-meteo.com/en/terms',
    min_trend_years: 10,
    ...rest,
  };
}
