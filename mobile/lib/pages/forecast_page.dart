// Forecast — the pics/ mockup's Forecast: a two-way switch over a list of
// day rows. GET /facts serves today, tonight and tomorrow (no hourly series,
// no structured 5-day breakdown), so the switch is "Days" (the rows) and
// "Details" (each period's figures plus provenance) rather than the
// mockup's "5 Days" / "Hourly"; the banner at the foot hands a 5-day
// question to Chat, where /ask narrates it.
import 'package:flutter/material.dart';

import '../components/app_shell.dart';
import '../components/common.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../components/weather_glyph.dart';
import '../facts_client.dart';
import '../format.dart';
import '../state/ui_prefs.dart';
import '../state/weather_store.dart';
import '../persona_theme.dart';
import '../theme.dart';
import 'best_window_page.dart';

enum _View { days, details }

class ForecastPage extends StatefulWidget {
  const ForecastPage({super.key});

  @override
  State<ForecastPage> createState() => _ForecastPageState();
}

class _ForecastPageState extends State<ForecastPage> {
  _View _view = _View.days;

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final weather = WeatherStore.of(context);
    final nav = ShellNav.of(context);
    final city = prefs.cityInfo.name;

    return PageFrame(
      onRefresh: weather.refresh,
      children: [
        PageHeader(title: 'Forecast', subtitle: prefs.personaInfo.forecastLead),
        const SizedBox(height: AppSpace.md),
        _Switch(value: _view, onChanged: (v) => setState(() => _view = v)),
        const SizedBox(height: AppSpace.md),
        ..._body(weather),
        const SizedBox(height: AppSpace.sm),
        InfoBanner(
          icon: prefs.personaInfo.icon,
          title: 'Need more days?',
          body: 'Ask for a 5-day forecast for $city in Chat.',
          onTap: () => nav.ask('5-day forecast for $city'),
        ),
        const SizedBox(height: AppSpace.sm),
        InfoBanner(
          icon: Icons.schedule,
          title: "When's the best time to go outside?",
          body: 'See the best window today or tomorrow, and compare two times.',
          onTap: () => openBestWindow(context),
        ),
      ],
    );
  }

  List<Widget> _body(WeatherStore weather) {
    if (weather.error != null) {
      return [
        ErrorPanel(
          icon: Icons.wifi_off,
          title: 'Forecast unavailable',
          message: weather.error!.message,
          onRetry: weather.refresh,
        ),
        const SizedBox(height: AppSpace.sm),
      ];
    }
    if (weather.today == null) {
      return [const LoadingPanel('Loading the forecast…'), const SizedBox(height: AppSpace.sm)];
    }

    final rows = [
      ('Today', weather.today, 0, false),
      ('Tonight', weather.tonight, 0, true),
      ('Tomorrow', weather.tomorrow, 1, false),
    ];
    return [
      for (final (label, result, offset, night) in rows) ...[
        _view == _View.days
            ? _DayRow(label: label, result: result, dayOffset: offset, night: night)
            : _DetailCard(label: label, result: result, dayOffset: offset, night: night),
        const SizedBox(height: 10),
      ],
      if (_view == _View.details) ...[_ProvenanceCard(weather: weather), const SizedBox(height: 10)],
    ];
  }
}

/// The mockup's "5 Days | Hourly" pill switch.
class _Switch extends StatelessWidget {
  final _View value;
  final ValueChanged<_View> onChanged;
  const _Switch({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    Widget tab(_View v, String label) {
      final selected = v == value;
      return Expanded(
        child: Semantics(
          selected: selected,
          button: true,
          child: Material(
            color: Colors.transparent,
            borderRadius: BorderRadius.circular(999),
            child: Ink(
              decoration: BoxDecoration(
                gradient: selected ? t.accentGradient : null,
                borderRadius: BorderRadius.circular(999),
              ),
              child: InkWell(
                borderRadius: BorderRadius.circular(999),
                onTap: () => onChanged(v),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  child: Text(
                    label,
                    textAlign: TextAlign.center,
                    style: AppText.labelMd.copyWith(
                      color: selected ? t.onPrimary : t.ink,
                      fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(color: t.tint, borderRadius: BorderRadius.circular(999)),
      child: Row(children: [tab(_View.days, 'Days'), const SizedBox(width: 4), tab(_View.details, 'Details')]),
    );
  }
}

/// Label + date | glyph | high / low + condition.
class _DayRow extends StatelessWidget {
  final String label;
  final FactsResult? result;
  final int dayOffset;
  final bool night;
  const _DayRow({required this.label, required this.result, required this.dayOffset, required this.night});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final r = result;
    final hasData = r?.hasData == true;
    final high = r?.number('high_c');
    final low = r?.number('low_c');
    final String temps;
    if (!hasData) {
      temps = '—';
    } else if (night) {
      // Tonight's high/low are the whole day's — show only the low.
      temps = low == null ? '—' : 'Low ${prefs.temp(low)}°';
    } else {
      temps = '${high == null ? '—' : prefs.temp(high)}° / ${low == null ? '—' : prefs.temp(low)}°';
    }

    return AppCard(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 12),
      child: Row(
        children: [
          Expanded(
            flex: 4,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
                Text(
                  istDayMonth(r?.issued, fallbackOffsetDays: dayOffset),
                  style: AppText.bodySm.copyWith(color: t.inkMuted),
                ),
              ],
            ),
          ),
          WeatherGlyph(r?.condition, night: night, size: 40),
          const SizedBox(width: AppSpace.md),
          Expanded(
            flex: 5,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  temps,
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
                ),
                Text(
                  hasData ? sentenceCase(r!.conditionLabel) : (r?.message ?? 'No forecast for this period.'),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.bodySm.copyWith(color: t.inkMuted),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// One period's figures, as served.
class _DetailCard extends StatelessWidget {
  final String label;
  final FactsResult? result;
  final int dayOffset;
  final bool night;
  const _DetailCard({required this.label, required this.result, required this.dayOffset, required this.night});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final r = result;
    final hasData = r?.hasData == true;
    final high = r?.number('high_c');
    final low = r?.number('low_c');
    final rain = r?.number('rain_probability_pct');

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              WeatherGlyph(r?.condition, night: night, size: 32),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  '$label, ${istDayMonth(r?.issued, fallbackOffsetDays: dayOffset)}',
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
              ),
              if (hasData) LiveBadge(live: r!.isLive),
            ],
          ),
          const SizedBox(height: 12),
          if (!hasData)
            Text(r?.message ?? 'No forecast for this period.', style: AppText.bodySm.copyWith(color: t.inkMuted))
          else
            Row(
              children: [
                Expanded(
                  child: _Figure(Icons.umbrella_outlined, 'Rain chance', rain == null ? '—' : '${rain.round()}%'),
                ),
                Expanded(
                  child: night
                      ? _Figure(Icons.nights_stay_outlined, 'Overnight low', low == null ? '—' : prefs.tempLabel(low))
                      : _Figure(Icons.thermostat, 'High', high == null ? '—' : prefs.tempLabel(high)),
                ),
                Expanded(
                  child: night
                      ? _Figure(Icons.cloud_outlined, 'Sky', sentenceCase(r!.conditionLabel))
                      : _Figure(Icons.thermostat_auto_outlined, 'Low', low == null ? '—' : prefs.tempLabel(low)),
                ),
              ],
            ),
        ],
      ),
    );
  }
}

class _Figure extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _Figure(this.icon, this.label, this.value);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 14, color: t.primary),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                label,
                overflow: TextOverflow.ellipsis,
                style: AppText.bodySm.copyWith(color: t.inkMuted),
              ),
            ),
          ],
        ),
        const SizedBox(height: 2),
        Text(value, style: AppText.headlineSm.copyWith(color: t.ink, fontSize: 16)),
      ],
    );
  }
}

class _ProvenanceCard extends StatelessWidget {
  final WeatherStore weather;
  const _ProvenanceCard({required this.weather});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final source = weather.today?.source;
    return AppCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const IconDisc(Icons.verified_outlined, size: 36),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Forecast Provenance',
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 2),
                Text(
                  source == null
                      ? 'Every figure on this page is read directly from the forecast feed — never generated by the language model.'
                      : 'As served by $source. Every figure above is read directly from that response — '
                            'never generated by the language model.',
                  style: AppText.bodySm.copyWith(color: t.inkMuted),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
