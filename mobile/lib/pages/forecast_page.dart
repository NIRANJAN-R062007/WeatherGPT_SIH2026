// Forecast — the pics/ mockup's Forecast: a "Days | Hourly" pill switch.
// Days is GET /forecast/daily's list (up to 10 days; tap a day for its rain,
// wind, humidity, UV and sun times), Hourly is /forecast/hourly's next 24
// hours as a strip under a temperature curve. Every figure is the feed's
// own, never generated. A backend from before those routes (404) gets the
// /facts rows (today, tonight, tomorrow) and the banner that hands a 5-day
// question to Chat, as before. Saved figures (backend unreachable) show
// under a banner saying when they were saved.
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
import '../i18n.dart';

enum _View { days, hourly }

class ForecastPage extends StatefulWidget {
  const ForecastPage({super.key});

  @override
  State<ForecastPage> createState() => _ForecastPageState();
}

class _ForecastPageState extends State<ForecastPage> {
  _View _view = _View.days;

  /// The day list's expanded row.
  int? _open;

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final weather = WeatherStore.of(context);
    final nav = ShellNav.of(context);
    final city = tr(context, prefs.cityInfo.name);

    return PageFrame(
      onRefresh: weather.refresh,
      children: [
        PageHeader(title: 'Forecast', subtitle: prefs.personaInfo.forecastLead),
        const SizedBox(height: AppSpace.md),
        if (weather.savedAt case final savedAt?) ...[
          SavedDataBanner(
            message: "Couldn't reach the weather service. These figures were saved at {time}.",
            messageArgs: {'time': savedTimeLabel(savedAt, langOf(context))},
            onRetry: weather.refresh,
          ),
          const SizedBox(height: AppSpace.md),
        ],
        _Switch(value: _view, onChanged: (v) => setState(() => _view = v)),
        const SizedBox(height: AppSpace.md),
        ...(_view == _View.days ? _days(weather) : _hours(weather, city)),
        const SizedBox(height: AppSpace.sm),
        if (!weather.hasDaily && !weather.dailyPending) ...[
          InfoBanner(
            icon: prefs.personaInfo.icon,
            title: 'Need more days?',
            body: tr(context, 'Ask for a 5-day forecast for {city} in Chat.', {'city': city}),
            onTap: () => nav.ask(tr(context, '5-day forecast for {city}', {'city': city})),
          ),
          const SizedBox(height: AppSpace.sm),
        ],
        InfoBanner(
          icon: Icons.schedule,
          title: "When's the best time to go outside?",
          body: 'See the best window today or tomorrow, and compare two times.',
          onTap: () => openBestWindow(context),
        ),
      ],
    );
  }

  List<Widget> _days(WeatherStore weather) {
    if (weather.hasDaily) {
      final daily = weather.daily!;
      return [
        for (final (i, day) in daily.entries.indexed) ...[
          _DayTile(day: day, expanded: _open == i, onTap: () => setState(() => _open = _open == i ? null : i)),
          const SizedBox(height: 10),
        ],
        _ProvenanceCard(source: daily.source, savedAt: daily.savedAt),
        const SizedBox(height: 10),
      ];
    }
    if (weather.dailyPending) {
      return [const LoadingPanel('Loading the forecast…'), const SizedBox(height: AppSpace.sm)];
    }
    return _factsRows(weather);
  }

  /// Today / tonight / tomorrow from /facts, for a backend without
  /// /forecast/daily.
  List<Widget> _factsRows(WeatherStore weather) {
    if (weather.error != null) {
      return [
        ErrorPanel(
          icon: Icons.wifi_off,
          title: 'Forecast unavailable',
          message: weather.error!.message,
          messageArgs: weather.error!.args,
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
        _DayRow(label: label, result: result, dayOffset: offset, night: night),
        const SizedBox(height: 10),
      ],
    ];
  }

  List<Widget> _hours(WeatherStore weather, String city) {
    final t = PersonaTheme.of(context);
    if (weather.hasHourly) {
      return [
        _HourlyStrip(hourly: weather.hourly!),
        const SizedBox(height: 10),
        _ProvenanceCard(source: weather.hourly!.source, savedAt: weather.hourly!.savedAt),
        const SizedBox(height: 10),
      ];
    }
    if (weather.hourlyPending) {
      return [const LoadingPanel('Loading the hourly forecast…'), const SizedBox(height: AppSpace.sm)];
    }
    final error = weather.hourlyError;
    if (error != null && error.status != 404) {
      return [
        ErrorPanel(
          icon: Icons.wifi_off,
          title: 'Hourly forecast unavailable',
          message: error.message,
          messageArgs: error.args,
          onRetry: weather.refresh,
        ),
        const SizedBox(height: AppSpace.sm),
      ];
    }
    return [
      AppCard(
        child: Text(
          error != null
              ? tr(context, "This weather service doesn't serve an hourly forecast yet.")
              : tr(context, 'No hourly forecast for {city} right now.', {'city': city}),
          style: AppText.bodyMd.copyWith(color: t.inkMuted),
        ),
      ),
      const SizedBox(height: AppSpace.sm),
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
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: kMinInteractiveDimension),
                  child: Center(
                    child: Text(
                      tr(context, label),
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
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(color: t.tint, borderRadius: BorderRadius.circular(999)),
      child: Row(children: [tab(_View.days, 'Days'), const SizedBox(width: 4), tab(_View.hourly, 'Hourly')]),
    );
  }
}

/// One /forecast/daily day: name + date | glyph | high / low + condition |
/// rain chance; tapped, the rest of its figures.
class _DayTile extends StatelessWidget {
  final ForecastDay day;
  final bool expanded;
  final VoidCallback onTap;
  const _DayTile({required this.day, required this.expanded, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final lang = langOf(context);
    final high = day.number('high_c');
    final low = day.number('low_c');
    final rain = day.number('rain_probability_pct');
    final date = day.date;
    final name = Text(
      forecastDayName(day.label, date, lang),
      style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
    );
    final dateText = date == null ? null : Text(dayMonth(date, lang), style: AppText.bodySm.copyWith(color: t.inkMuted));
    // At large text sizes the day's name gets its own line, so it isn't
    // broken mid-word in a narrow column.
    final large = isLargeText(context);
    // Read out as a sentence: on screen the rain chance is a droplet and a
    // number, which a screen reader would read as a bare "15%".
    final spoken = tr(context, '{day}, {date}: {condition}, high {high}, low {low}, {rain}% chance of rain', {
      'day': forecastDayName(day.label, date, lang),
      'date': date == null ? '' : dayMonth(date, lang),
      'condition': day.conditionLabel ?? '',
      'high': high == null ? '—' : '${prefs.temp(high)}°',
      'low': low == null ? '—' : '${prefs.temp(low)}°',
      'rain': rain?.round() ?? '—',
    });

    return AppCard(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 12),
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            label: spoken,
            excludeSemantics: true,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (large) ...[
                  Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [name, ?dateText]),
                  const SizedBox(height: 4),
                ],
                Row(
                  children: [
                    if (!large)
                      Expanded(
                        flex: 4,
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [name, ?dateText]),
                      ),
                    WeatherGlyph(day.condition, size: 36),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 5,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${high == null ? '—' : prefs.temp(high)}° / ${low == null ? '—' : prefs.temp(low)}°',
                            style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
                          ),
                          Text(
                            sentenceCase(day.conditionLabel),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.bodySm.copyWith(color: t.inkMuted),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: AppSpace.sm),
                    Icon(Icons.water_drop_outlined, size: 14, color: t.primary),
                    const SizedBox(width: 2),
                    Text(
                      rain == null ? '—' : '${rain.round()}%',
                      style: AppText.bodySm.copyWith(color: t.ink, fontWeight: FontWeight.w600),
                    ),
                    Icon(expanded ? Icons.expand_less : Icons.expand_more, size: 20, color: t.inkMuted),
                  ],
                ),
              ],
            ),
          ),
          if (expanded) ...[
            const SizedBox(height: 12),
            Divider(height: 1, color: t.cardBorder),
            const SizedBox(height: 12),
            _DayFigures(day: day),
          ],
        ],
      ),
    );
  }
}

/// An expanded day's figures, three to a row, then its night.
class _DayFigures extends StatelessWidget {
  final ForecastDay day;
  const _DayFigures({required this.day});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final lang = langOf(context);
    String pct(String key) {
      final v = day.number(key);
      return v == null ? '—' : '${v.round()}%';
    }

    final rainMm = day.number('rain_mm');
    final wind = day.number('wind_kmh');
    final uv = day.number('uv_index');
    final sunrise = DateTime.tryParse(day.sunrise ?? '');
    final sunset = DateTime.tryParse(day.sunset ?? '');
    final figures = [
      _Figure(Icons.umbrella_outlined, 'Rain chance', pct('rain_probability_pct')),
      _Figure(Icons.water_drop_outlined, 'Rainfall', rainMm == null ? '—' : millimetres(rainMm)),
      _Figure(Icons.air, 'Wind', wind == null ? '—' : '${wind.round()} km/h'),
      _Figure(Icons.opacity, 'Humidity', pct('humidity_pct')),
      _Figure(Icons.wb_sunny_outlined, 'UV index', uv == null ? '—' : '${uv.round()}'),
      _Figure(
        Icons.timelapse,
        'Daylight',
        sunrise == null || sunset == null ? '—' : hoursMinutes(sunset.difference(sunrise), lang),
      ),
      _Figure(Icons.wb_twilight, 'Sunrise', day.sunrise == null ? '—' : istClock(day.sunrise)),
      _Figure(Icons.nights_stay_outlined, 'Sunset', day.sunset == null ? '—' : istClock(day.sunset)),
      _Figure(Icons.umbrella_outlined, 'Rain at night', pct('night_rain_probability_pct')),
    ];

    // Two to a row at large text sizes, so the labels keep their words.
    final perRow = isLargeText(context) ? 2 : 3;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < figures.length; i += perRow) ...[
          if (i > 0) const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final figure in figures.sublist(i, i + perRow > figures.length ? figures.length : i + perRow))
                Expanded(child: figure),
              // A short last row keeps the columns lined up.
              for (var pad = figures.length; pad < i + perRow; pad++) const Expanded(child: SizedBox()),
            ],
          ),
        ],
        if (day.nightConditionLabel != null) ...[
          const SizedBox(height: 12),
          Row(
            children: [
              WeatherGlyph(day.nightCondition, night: true, size: 22),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Text(
                  tr(context, 'Night: {condition}', {'condition': day.nightConditionLabel}),
                  style: AppText.bodySm.copyWith(color: t.inkMuted),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

/// The next 24 hours: a temperature curve over a row of hour columns
/// (time, glyph, rain chance), scrolled sideways together. A caption marks
/// the first hour ("Now") and each new day. Columns and curve grow with the
/// system text size, so larger text still fits; the strip just scrolls more.
class _HourlyStrip extends StatelessWidget {
  final HourlyForecast hourly;
  const _HourlyStrip({required this.hourly});

  static const double _column = 58;
  static const double _curve = 64;

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final lang = langOf(context);
    final hours = hourly.entries;
    final first = DateTime.tryParse(hours.first.date ?? '');
    final textScaler = MediaQuery.textScalerOf(context);
    final grow = (textScaler.scale(12) / 12).clamp(1.0, 3.0);
    final column = _column * grow;
    final caption = AppText.bodySm.copyWith(color: t.primary, fontWeight: FontWeight.w700, fontSize: 11);

    String? captionFor(int i) {
      if (i == 0) return tr(context, 'Now');
      if (hours[i].date == hours[i - 1].date) return null;
      final date = DateTime.tryParse(hours[i].date ?? '');
      final label = first != null && date != null && date.difference(first).inDays == 1 ? 'tomorrow' : '';
      return forecastDayName(label, date, lang);
    }

    return AppCard(
      wash: true,
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: AppSpace.sm),
        child: SizedBox(
          width: hours.length * column,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  for (var i = 0; i < hours.length; i++)
                    SizedBox(
                      width: column,
                      child: switch (captionFor(i)) {
                        null => const SizedBox.shrink(),
                        // Shrunk rather than cut: "இப்போது" is wider than a column.
                        final text => FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Text(text, maxLines: 1, style: caption),
                        ),
                      },
                    ),
                ],
              ),
              CustomPaint(
                size: Size(hours.length * column, _curve * grow),
                painter: _TempCurve(
                  temps: [for (final h in hours) h.number('temp_c')],
                  label: (c) => '${prefs.temp(c)}°',
                  color: t.primary,
                  textStyle: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600, fontSize: 13),
                  textScaler: textScaler,
                ),
              ),
              Row(
                children: [
                  for (final h in hours)
                    Semantics(
                      label: tr(context, '{time}: {temp}, {condition}, {rain}% chance of rain', {
                        'time': h.localTime,
                        'temp': h.number('temp_c') == null ? '—' : prefs.tempLabel(h.number('temp_c')!),
                        'condition': h.conditionLabel ?? '',
                        'rain': h.number('rain_probability_pct')?.round() ?? '—',
                      }),
                      excludeSemantics: true,
                      child: SizedBox(
                        width: column,
                        child: Column(
                          children: [
                            WeatherGlyph(h.condition, night: h.isNight, size: 28),
                            const SizedBox(height: 4),
                            Text(h.localTime, style: AppText.bodySm.copyWith(color: t.ink)),
                            const SizedBox(height: 2),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.water_drop_outlined, size: 11, color: t.primary),
                                Text(
                                  h.number('rain_probability_pct') == null
                                      ? '—'
                                      : '${h.number('rain_probability_pct')!.round()}%',
                                  style: AppText.bodySm.copyWith(color: t.inkMuted, fontSize: 11),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A smooth line through each hour's temperature, centred in its column,
/// with the value above the point, at the system text size. Missing hours
/// break the line.
class _TempCurve extends CustomPainter {
  final List<num?> temps;
  final String Function(num celsius) label;
  final Color color;
  final TextStyle textStyle;
  final TextScaler textScaler;
  _TempCurve({
    required this.temps,
    required this.label,
    required this.color,
    required this.textStyle,
    required this.textScaler,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final known = temps.whereType<num>();
    if (known.isEmpty) return;
    final lo = known.reduce((a, b) => a < b ? a : b).toDouble();
    final hi = known.reduce((a, b) => a > b ? a : b).toDouble();
    final column = size.width / temps.length;
    final top = textScaler.scale(20) + 4; // room for a label over the highest point
    final bottom = size.height - 6;
    Offset? at(int i) {
      final c = temps[i];
      if (c == null) return null;
      final y = hi == lo ? (top + bottom) / 2 : bottom - (c - lo) / (hi - lo) * (bottom - top);
      return Offset(column * (i + 0.5), y);
    }

    final line = Paint()
      ..color = color
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    final dot = Paint()..color = color;
    Path? path;
    Offset? prev;
    for (var i = 0; i < temps.length; i++) {
      final p = at(i);
      if (p == null) {
        if (path != null) canvas.drawPath(path, line);
        path = prev = null;
        continue;
      }
      if (path == null || prev == null) {
        path = Path()..moveTo(p.dx, p.dy);
      } else {
        final mid = (prev.dx + p.dx) / 2;
        path.cubicTo(mid, prev.dy, mid, p.dy, p.dx, p.dy);
      }
      prev = p;
      canvas.drawCircle(p, 3, dot);
      final text = TextPainter(
        text: TextSpan(text: label(temps[i]!), style: textStyle),
        textDirection: TextDirection.ltr,
        textScaler: textScaler,
      )..layout();
      text.paint(canvas, Offset(p.dx - text.width / 2, p.dy - text.height - 4));
    }
    if (path != null) canvas.drawPath(path, line);
  }

  @override
  bool shouldRepaint(_TempCurve old) =>
      old.temps != temps || old.color != color || old.textStyle != textStyle || old.textScaler != textScaler;
}

/// Label + date | glyph | high / low + condition — a /facts period, for a
/// backend without /forecast/daily.
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
      temps = low == null ? '—' : tr(context, 'Low {temp}°', {'temp': prefs.temp(low)});
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
                  tr(context, label),
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
                Text(
                  istDayMonth(r?.issued, fallbackOffsetDays: dayOffset, lang: langOf(context)),
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
                  hasData
                      ? sentenceCase(r!.conditionLabel)
                      : (r?.message ?? tr(context, 'No forecast for this period.')),
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
              // Wraps rather than cuts a long translation short.
              child: Text(tr(context, label), style: AppText.bodySm.copyWith(color: t.inkMuted)),
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
  final String? source;

  /// When the series shown was saved, if it's a saved copy.
  final DateTime? savedAt;
  const _ProvenanceCard({required this.source, this.savedAt});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
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
                  tr(context, 'Forecast Provenance'),
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 2),
                Text(
                  source == null
                      ? tr(
                          context,
                          'Every figure on this page is read directly from the forecast feed — never generated by the language model.',
                        )
                      : tr(
                          context,
                          'As served by {source}. Every figure above is read directly from that response — never generated by the language model.',
                          {'source': source},
                        ),
                  style: AppText.bodySm.copyWith(color: t.inkMuted),
                ),
                if (savedAt case final saved?)
                  Text(
                    tr(context, 'Saved on this phone at {time}.', {'time': savedTimeLabel(saved, langOf(context))}),
                    style: AppText.bodySm.copyWith(color: t.ink, fontWeight: FontWeight.w600),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
