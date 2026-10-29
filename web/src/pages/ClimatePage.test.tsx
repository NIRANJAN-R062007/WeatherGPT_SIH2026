// Climate trends (CLM-5): what the page says and draws for each kind of answer —
// the source line, credit and "computed by WeatherGPT" note; the three trend
// wordings (clear, can't tell, too few years); years with missing days left out
// as gaps; a dated snapshot; and a chart that never draws a missing year as
// zero. Rendered to static markup, as AlertsPage.test.tsx does.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { ClimateMetric, ClimatePeriod, ClimateResponse } from '../lib/climate';
import { seriesOf, trendOf } from '../lib/climate';
import { climateBody, LABEL, trend } from '../test/climateFixture';
import { UiPrefsProvider } from '../state/UiPrefsContext';
import { ClimateBody, ClimateChart, ClimateSource } from './ClimatePage';

const noop = () => {};

function body(data: ClimateResponse, metric: ClimateMetric = 'rain', period: ClimatePeriod = 'year') {
  return renderToStaticMarkup(
    <UiPrefsProvider>
      <ClimateBody data={data} metric={metric} period={period} onMetric={noop} onPeriod={noop} />
    </UiPrefsProvider>,
  );
}

function chart(data: ClimateResponse, metric: ClimateMetric, period: ClimatePeriod = 'year') {
  return renderToStaticMarkup(
    <ClimateChart series={seriesOf(data, period, metric)} metric={metric} trend={trendOf(data, period, metric)} label="chart" />,
  );
}

const count = (html: string, needle: string) => html.split(needle).length - 1;

describe('Climate trends: the chart', () => {
  it('rainfall is one bar per complete year (30 of 31) and a dashed trend line', () => {
    const html = chart(climateBody(), 'rain');
    expect(count(html, '<rect')).toBe(30);
    expect(html).toContain('stroke-dasharray="9 5"');
  });

  it('temperature is a line with a dot per complete year, and the line breaks at a missing year', () => {
    const html = chart(climateBody({ missingYears: [2000, 2026] }), 'temperature');
    expect(count(html, '<circle')).toBe(29);
    expect(count(html, '<polyline')).toBe(2); // 1996–1999 and 2001–2025
  });

  it('draws no trend line when there is no slope', () => {
    const data = climateBody({ yearRain: trend({ status: 'insufficient_data', slope_per_decade: null, mean: null }) });
    expect(chart(data, 'rain')).not.toContain('stroke-dasharray="9 5"');
  });

  it('draws nothing at all for a period with no complete year', () => {
    const data = climateBody();
    data.seasonal = (data.seasonal ?? []).map((r) => ({ ...r, rain_mm: null }));
    expect(chart(data, 'rain', 'monsoon')).toBe('');
  });

  it('a missing year is not drawn as a zero-height bar', () => {
    const html = chart(climateBody({ missingYears: [1996, 1997, 2026] }), 'rain');
    expect(count(html, '<rect')).toBe(28);
  });
});

describe('Climate trends: the page body', () => {
  it('names the chart, and lists the same figures as text', () => {
    const html = body(climateBody());
    expect(html).toContain('Rainfall — Whole year');
    expect(html).toContain('aria-label="Chart: Rainfall — Whole year, 1996 to 2026. The same figures are listed below."');
    expect(html).toContain('Show every year');
    expect(html).toContain('940 mm');
    expect(html).toContain('Missing days — left out');
  });

  it('a trend that is not clear says it can\'t be told apart, and that this is not "no change"', () => {
    const html = body(climateBody());
    expect(html).toContain('+84.0 mm per decade (± 54.6 mm) over 30 complete years, 1996–2025');
    expect(html).toContain("can&#x27;t be told apart from year-to-year variation");
    expect(html).toContain('does not mean nothing has changed');
    expect(html).not.toContain('clear of year-to-year variation');
  });

  it('a clear trend says so at the 95% level', () => {
    const html = body(climateBody(), 'temperature');
    expect(html).toContain('+0.24 °C per decade (± 0.04 °C) over 30 complete years');
    expect(html).toContain('clear of year-to-year variation at the 95% level');
    expect(html).not.toContain('told apart');
  });

  it('too few complete years is "No trend", not a line', () => {
    const html = body(climateBody(), 'temperature', 'monsoon');
    expect(html).toContain('No trend');
    expect(html).toContain('at least 10 are needed, and there are 4');
    expect(html).not.toContain('Trend line');
  });

  it('says how many years with missing days are left out, singular and plural', () => {
    expect(body(climateBody())).toContain('One year with missing days is left out, not drawn as zero.');
    expect(body(climateBody({ missingYears: [2000, 2026] }))).toContain(
      '2 years with missing days are left out, not drawn as zero.',
    );
    expect(body(climateBody({ missingYears: [] }))).not.toContain('with missing days are left out');
  });

  it('a live answer has no snapshot banner; an offline snapshot gives its date in IST', () => {
    expect(body(climateBody())).not.toContain('Snapshot taken');
    // 12:51 UTC is 18:21 in India.
    expect(body(climateBody({ is_live: false }))).toContain('Snapshot taken 29 Oct, 18:21 IST — not live data.');
  });

  it('every period and both metrics are offered', () => {
    const html = body(climateBody());
    for (const label of ['Whole year', 'Winter (Jan–Feb)', 'Pre-monsoon (Mar–May)', 'Monsoon (Jun–Sep)', 'Post-monsoon (Oct–Dec)', 'Rainfall', 'Temperature']) {
      expect(html).toContain(label);
    }
  });
});

describe('Climate trends: the source', () => {
  const html = renderToStaticMarkup(
    <UiPrefsProvider>
      <ClimateSource data={climateBody()} />
    </UiPrefsProvider>,
  );

  it('shows the source line exactly, the credit link, and that WeatherGPT computed the figures', () => {
    expect(html).toContain(LABEL);
    expect(html).toContain('href="https://open-meteo.com/"');
    expect(html).toContain('Weather data by Open-Meteo.com');
    expect(html).toContain('computed by WeatherGPT');
    expect(html).toContain('not IMD&#x27;s declared monsoon onset');
  });

  it('links the licence and the terms, opened safely', () => {
    expect(html).toContain('href="https://open-meteo.com/en/licence"');
    expect(html).toContain('href="https://open-meteo.com/en/terms"');
    expect(count(html, 'rel="noopener noreferrer"')).toBe(3);
  });
});
