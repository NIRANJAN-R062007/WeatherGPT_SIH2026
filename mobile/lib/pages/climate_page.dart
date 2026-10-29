// Climate trends — opened from the drawer's "Climate trends" item (plan.md §8
// Phase 5, CLM-5): how a demo city's rainfall and mean temperature have
// changed over about 30 years, from Open-Meteo's ERA5 reanalysis
// (climate_client.dart; services/orchestrator/climate.py). The chart is a
// picture of the yearly figures; the trend sentence, and the list of every
// year under it, carry the same numbers as text.
//
// Every figure and the trend are computed server-side, in plain code, never by
// an LLM; this page only draws and words them. The source line "Open-Meteo /
// ERA5 reanalysis, not IMD station data", the credit link and the "computed by
// WeatherGPT" note are on the page in every state. A year with missing days is
// left out of the chart (a gap, never zero), and a trend that isn't
// statistically clear is worded "can't be told apart from year-to-year
// variation", never "no change" (plan.md §2 principle 3; climate.py's notes).
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../climate_client.dart';
import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../format.dart';
import '../i18n.dart';
import '../persona_theme.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';

Future<void> openClimate(BuildContext context) {
  return Navigator.of(
    context,
  ).push(MaterialPageRoute<void>(builder: (_) => const ClimatePage()));
}

class ClimatePage extends StatefulWidget {
  /// Where climate history comes from; tests pass a stub.
  final ClimateFetcher fetcher;
  const ClimatePage({super.key, this.fetcher = fetchClimate});

  @override
  State<ClimatePage> createState() => _ClimatePageState();
}

class _ClimatePageState extends State<ClimatePage> {
  String? _city;
  bool _loading = false;
  ClimateData? _data;
  ClimateError? _error;
  int _requestId = 0;
  ClimateMetric _metric = ClimateMetric.rain;
  ClimatePeriod _period = ClimatePeriod.year;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Fetch on first build and whenever the shared city changes. A build
    // always follows, so no setState here.
    final city = UiPrefs.of(context).city;
    if (city != _city) _load(city);
  }

  void _load(String city) {
    if (city != _city) _data = null;
    _city = city;
    _loading = true;
    _error = null;
    _fetch(++_requestId, city);
  }

  Future<void> _fetch(int id, String city) async {
    try {
      final data = await widget.fetcher(city);
      if (!mounted || id != _requestId) return;
      setState(() {
        _data = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || id != _requestId) return;
      setState(() {
        _error = e is ClimateError
            ? e
            : ClimateError(
                ClimateErrorKind.network,
                'Something went wrong talking to the climate service.',
              );
        _data = null;
        _loading = false;
      });
    }
  }

  Future<void> _reload() async {
    final city = UiPrefs.read(context).city;
    setState(() => _load(city));
  }

  @override
  Widget build(BuildContext context) {
    final city = tr(context, UiPrefs.of(context).cityInfo.name);
    final data = _data;
    return SubPageScaffold(
      body: PageFrame(
        onRefresh: _reload,
        children: [
          PageHeader(
            title: 'Climate trends',
            subtitle: tr(
              context,
              'How rainfall and temperature in {city} have changed over about 30 years.',
              {'city': city},
            ),
          ),
          const SizedBox(height: AppSpace.lg),
          if (_loading)
            const LoadingPanel('Fetching the climate history…')
          else if (_error != null)
            ErrorPanel(
              icon: Icons.wifi_off,
              title: 'Climate trends unavailable',
              message: _error!.message,
              messageArgs: _error!.args,
              onRetry: _reload,
            )
          else if (data != null && data.unavailable)
            _Unavailable(data, city)
          else if (data != null)
            ..._ready(data, city),
        ],
      ),
    );
  }

  List<Widget> _ready(ClimateData data, String city) {
    final series = data.series(_period, _metric);
    final trend = data.trend(_period, _metric);
    return [
      if (!data.isLive) ...[
        _SnapshotBanner(retrievedAt: data.retrievedAt),
        const SizedBox(height: AppSpace.sm),
      ],
      _PillSwitch<ClimateMetric>(
        value: _metric,
        options: const [
          (ClimateMetric.rain, 'Rainfall'),
          (ClimateMetric.temperature, 'Temperature'),
        ],
        onChanged: (m) => setState(() => _metric = m),
      ),
      const SizedBox(height: AppSpace.sm),
      _PeriodPicker(
        value: _period,
        onChanged: (p) => setState(() => _period = p),
      ),
      const SizedBox(height: AppSpace.md),
      _ChartCard(
        data: data,
        metric: _metric,
        period: _period,
        series: series,
        trend: trend,
        city: city,
      ),
      const SizedBox(height: AppSpace.md),
      _TrendCard(
        metric: _metric,
        period: _period,
        trend: trend,
        minYears: data.minTrendYears,
      ),
      const SizedBox(height: AppSpace.md),
      _YearList(metric: _metric, series: series),
      const SizedBox(height: AppSpace.lg),
      _Source(data: data),
    ];
  }
}

String metricName(ClimateMetric m) =>
    m == ClimateMetric.rain ? 'Rainfall' : 'Temperature';

String periodName(ClimatePeriod p) => switch (p) {
  ClimatePeriod.year => 'Whole year',
  ClimatePeriod.winter => 'Winter (Jan–Feb)',
  ClimatePeriod.preMonsoon => 'Pre-monsoon (Mar–May)',
  ClimatePeriod.monsoon => 'Monsoon (Jun–Sep)',
  ClimatePeriod.postMonsoon => 'Post-monsoon (Oct–Dec)',
};

/// "1,035 mm" / "28.2 °C"; [slope] keeps a sign and one more decimal for the
/// small temperature changes per decade.
String formatClimate(double v, ClimateMetric m, {bool slope = false}) {
  final digits = m == ClimateMetric.rain
      ? (slope || v.abs() < 100 ? 1 : 0)
      : (slope ? 2 : 1);
  var s = v.abs().toStringAsFixed(digits);
  if (m == ClimateMetric.rain && !slope) s = _group(s);
  final sign = v < 0 ? '−' : (slope ? '+' : '');
  return '$sign$s ${m.unit}';
}

String _group(String s) {
  final dot = s.indexOf('.');
  final whole = dot < 0 ? s : s.substring(0, dot);
  final rest = dot < 0 ? '' : s.substring(dot);
  final b = StringBuffer();
  for (var i = 0; i < whole.length; i++) {
    if (i > 0 && (whole.length - i) % 3 == 0) b.write(',');
    b.write(whole[i]);
  }
  return '$b$rest';
}

/// No data at all for this city: no verdict, and never zero rain or "no change".
class _Unavailable extends StatelessWidget {
  final ClimateData data;
  final String city;
  const _Unavailable(this.data, this.city);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AppCard(
          color: t.surfaceContainerLow,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const IconDisc(Icons.help_outline),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      tr(context, 'No climate history'),
                      style: AppText.labelMd.copyWith(
                        color: t.ink,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpace.sm),
              Text(
                tr(
                  context,
                  "The climate history for {city} isn't available right now — this can't be read as no change.",
                  {'city': city},
                ),
                style: AppText.bodyMd.copyWith(color: t.ink),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpace.md),
        _Source(data: data),
      ],
    );
  }
}

class _SnapshotBanner extends StatelessWidget {
  final String? retrievedAt;
  const _SnapshotBanner({required this.retrievedAt});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.tertiaryFixed,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 2),
            child: Icon(
              Icons.history,
              size: 14,
              color: AppColors.onTertiaryFixed,
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              tr(context, 'Snapshot taken {time} — not live data.', {
                'time': istTimestamp(retrievedAt),
              }),
              style: AppText.bodySm.copyWith(color: AppColors.onTertiaryFixed),
            ),
          ),
        ],
      ),
    );
  }
}

/// A pill switch like Forecast's "Days | Hourly".
class _PillSwitch<T> extends StatelessWidget {
  final T value;
  final List<(T, String)> options;
  final ValueChanged<T> onChanged;
  const _PillSwitch({
    required this.value,
    required this.options,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    Widget tab(T v, String label) {
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
                  constraints: const BoxConstraints(
                    minHeight: kMinInteractiveDimension,
                  ),
                  child: Center(
                    child: Text(
                      tr(context, label),
                      textAlign: TextAlign.center,
                      style: AppText.labelMd.copyWith(
                        color: selected ? t.onPrimary : t.ink,
                        fontWeight: selected
                            ? FontWeight.w700
                            : FontWeight.w500,
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
      decoration: BoxDecoration(
        color: t.tint,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        children: [
          for (var i = 0; i < options.length; i++) ...[
            if (i > 0) const SizedBox(width: 4),
            tab(options[i].$1, options[i].$2),
          ],
        ],
      ),
    );
  }
}

class _PeriodPicker extends StatelessWidget {
  final ClimatePeriod value;
  final ValueChanged<ClimatePeriod> onChanged;
  const _PeriodPicker({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final p in ClimatePeriod.values)
          Semantics(
            selected: p == value,
            button: true,
            child: Material(
              color: p == value ? t.primaryFixed : t.surfaceContainer,
              borderRadius: BorderRadius.circular(AppRadius.lg),
              child: InkWell(
                borderRadius: BorderRadius.circular(AppRadius.lg),
                onTap: () => onChanged(p),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    minHeight: kMinInteractiveDimension,
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    child: Text(
                      tr(context, periodName(p)),
                      style: AppText.labelMd.copyWith(
                        color: p == value ? t.onPrimaryFixed : t.ink,
                        fontWeight: p == value
                            ? FontWeight.w700
                            : FontWeight.w500,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _ChartCard extends StatelessWidget {
  final ClimateData data;
  final ClimateMetric metric;
  final ClimatePeriod period;
  final List<YearValue> series;
  final ClimateTrend? trend;
  final String city;
  const _ChartCard({
    required this.data,
    required this.metric,
    required this.period,
    required this.series,
    required this.trend,
    required this.city,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final known = series.where((p) => p.value != null).toList();
    final missing = series.length - known.length;
    final title = tr(context, '{metric} — {period}', {
      'metric': tr(context, metricName(metric)),
      'period': tr(context, periodName(period)),
    });
    final label = tr(
      context,
      'Chart: {title}, {from} to {to}. The same figures are listed below.',
      {
        'title': title,
        'from': series.isEmpty ? '' : series.first.year,
        'to': series.isEmpty ? '' : series.last.year,
      },
    );
    return AppCard(
      padding: const EdgeInsets.all(AppSpace.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: AppText.headlineSm.copyWith(
              color: t.ink,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          if (known.isEmpty)
            Text(
              tr(context, 'No complete years to draw for this period.'),
              style: AppText.bodyMd.copyWith(color: t.inkMuted),
            )
          else
            Semantics(
              label: label,
              image: true,
              excludeSemantics: true,
              child: AspectRatio(
                aspectRatio: 1.55,
                child: CustomPaint(
                  painter: ClimateChartPainter(
                    series: series,
                    metric: metric,
                    trend: trend,
                    bar: t.primary,
                    line: t.ink,
                    grid: t.outlineVariant,
                    label: t.inkMuted,
                  ),
                ),
              ),
            ),
          const SizedBox(height: AppSpace.sm),
          Wrap(
            spacing: AppSpace.md,
            runSpacing: AppSpace.xs,
            children: [
              _Key(
                painter: _KeyPainter(
                  metric == ClimateMetric.rain ? _Mark.bar : _Mark.dot,
                  t.primary,
                ),
                text: metric == ClimateMetric.rain
                    ? 'Total for the year'
                    : 'Average for the year',
              ),
              if (trend?.hasSlope ?? false)
                _Key(
                  painter: _KeyPainter(_Mark.dashed, t.ink),
                  text: 'Trend line',
                ),
            ],
          ),
          if (missing > 0) ...[
            const SizedBox(height: AppSpace.xs),
            Text(
              missing == 1
                  ? tr(context, 'One year with missing days is left out, not drawn as zero.')
                  : tr(context, '{count} years with missing days are left out, not drawn as zero.', {
                      'count': missing,
                    }),
              style: AppText.bodySm.copyWith(color: t.inkMuted),
            ),
          ],
        ],
      ),
    );
  }
}

enum _Mark { bar, dot, dashed }

class _Key extends StatelessWidget {
  final CustomPainter painter;
  final String text;
  const _Key({required this.painter, required this.text});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(width: 22, height: 12, child: CustomPaint(painter: painter)),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            tr(context, text),
            style: AppText.bodySm.copyWith(color: t.inkMuted),
          ),
        ),
      ],
    );
  }
}

class _KeyPainter extends CustomPainter {
  final _Mark mark;
  final Color color;
  const _KeyPainter(this.mark, this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..color = color;
    switch (mark) {
      case _Mark.bar:
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromLTWH(size.width / 2 - 4, 1, 8, size.height - 1),
            const Radius.circular(2),
          ),
          p,
        );
      case _Mark.dot:
        canvas.drawLine(
          Offset(0, size.height / 2),
          Offset(size.width, size.height / 2),
          p
            ..strokeWidth = 2
            ..style = PaintingStyle.stroke,
        );
        canvas.drawCircle(
          Offset(size.width / 2, size.height / 2),
          3,
          Paint()..color = color,
        );
      case _Mark.dashed:
        p
          ..strokeWidth = 2
          ..style = PaintingStyle.stroke;
        for (var x = 0.0; x < size.width; x += 7) {
          canvas.drawLine(
            Offset(x, size.height / 2),
            Offset(math.min(x + 4, size.width), size.height / 2),
            p,
          );
        }
    }
  }

  @override
  bool shouldRepaint(_KeyPainter old) => old.mark != mark || old.color != color;
}

/// Draws one series: bars for rainfall (they start at 0), a line with dots for
/// temperature, and the trend line through the complete years. A year with
/// missing data is a gap. No chart package: the figures are few and the
/// painter is small.
class ClimateChartPainter extends CustomPainter {
  final List<YearValue> series;
  final ClimateMetric metric;
  final ClimateTrend? trend;
  final Color bar, line, grid, label;

  const ClimateChartPainter({
    required this.series,
    required this.metric,
    required this.trend,
    required this.bar,
    required this.line,
    required this.grid,
    required this.label,
  });

  /// The trend's value in [year]: the fitted line passes through (mean year,
  /// mean value) of the complete years with the server's slope.
  double? _trendAt(double year, double meanYear) {
    final tr = trend;
    if (tr == null || !tr.hasSlope) return null;
    return tr.mean! + tr.slopePerDecade! / 10 * (year - meanYear);
  }

  void _text(
    Canvas canvas,
    String s,
    Offset at, {
    bool right = false,
    bool center = false,
  }) {
    final tp = TextPainter(
      text: TextSpan(
        text: s,
        style: TextStyle(fontSize: 10, color: label),
      ),
      textDirection: TextDirection.ltr,
      maxLines: 1,
    )..layout();
    final dx = right
        ? at.dx - tp.width
        : (center ? at.dx - tp.width / 2 : at.dx);
    tp.paint(canvas, Offset(dx, at.dy - tp.height / 2));
  }

  /// A step of 1, 2 or 5 × 10ⁿ giving about [target] intervals over [span].
  static double niceStep(double span, int target) {
    if (span <= 0) return 1;
    final raw = span / target;
    final mag = math.pow(10, (math.log(raw) / math.ln10).floor()).toDouble();
    final f = raw / mag;
    final nice = f <= 1 ? 1 : (f <= 2 ? 2 : (f <= 5 ? 5 : 10));
    return nice * mag;
  }

  @override
  void paint(Canvas canvas, Size size) {
    final known = [
      for (final p in series)
        if (p.value != null) p,
    ];
    if (known.isEmpty || series.isEmpty) return;

    const left = 40.0, bottom = 18.0, top = 6.0, right = 6.0;
    final plot = Rect.fromLTRB(
      left,
      top,
      size.width - right,
      size.height - bottom,
    );
    final firstYear = series.first.year, lastYear = series.last.year;
    final n = lastYear - firstYear + 1;
    final meanYear =
        known.map((p) => p.year).reduce((a, b) => a + b) / known.length;

    var lo = known.map((p) => p.value!).reduce(math.min);
    var hi = known.map((p) => p.value!).reduce(math.max);
    for (final y in [firstYear.toDouble(), lastYear.toDouble()]) {
      final tv = _trendAt(y, meanYear);
      if (tv != null) {
        lo = math.min(lo, tv);
        hi = math.max(hi, tv);
      }
    }
    if (metric == ClimateMetric.rain) lo = 0;
    final step = niceStep(hi - lo, 4);
    final yMin = metric == ClimateMetric.rain
        ? 0.0
        : (lo / step).floor() * step;
    var yMax = (hi / step).ceil() * step;
    if (yMax <= yMin) yMax = yMin + step;

    double xAt(num year) =>
        plot.left + (year - firstYear + 0.5) / n * plot.width;
    double yAt(double v) =>
        plot.bottom - (v - yMin) / (yMax - yMin) * plot.height;

    final gridPaint = Paint()
      ..color = grid.withValues(alpha: 0.6)
      ..strokeWidth = 0.7;
    for (var v = yMin; v <= yMax + step / 2; v += step) {
      final y = yAt(v);
      canvas.drawLine(Offset(plot.left, y), Offset(plot.right, y), gridPaint);
      _text(
        canvas,
        step < 1 ? v.toStringAsFixed(1) : v.toStringAsFixed(0),
        Offset(plot.left - 4, y),
        right: true,
      );
    }
    for (final year in {firstYear, firstYear + (n ~/ 2), lastYear}) {
      _text(canvas, '$year', Offset(xAt(year), plot.bottom + 10), center: true);
    }

    if (metric == ClimateMetric.rain) {
      final w = math.max(2.0, plot.width / n * 0.62);
      final paint = Paint()..color = bar;
      for (final p in known) {
        final x = xAt(p.year);
        canvas.drawRRect(
          RRect.fromRectAndCorners(
            Rect.fromLTRB(x - w / 2, yAt(p.value!), x + w / 2, plot.bottom),
            topLeft: const Radius.circular(2),
            topRight: const Radius.circular(2),
          ),
          paint,
        );
      }
    } else {
      final stroke = Paint()
        ..color = bar
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round;
      var path = Path();
      var open = false;
      for (final p in series) {
        if (p.value == null) {
          if (open) canvas.drawPath(path, stroke);
          path = Path();
          open = false;
          continue;
        }
        final at = Offset(xAt(p.year), yAt(p.value!));
        open ? path.lineTo(at.dx, at.dy) : path.moveTo(at.dx, at.dy);
        open = true;
      }
      if (open) canvas.drawPath(path, stroke);
      for (final p in known) {
        canvas.drawCircle(
          Offset(xAt(p.year), yAt(p.value!)),
          2.5,
          Paint()..color = bar,
        );
      }
    }

    final t0 = _trendAt(firstYear.toDouble(), meanYear);
    final t1 = _trendAt(lastYear.toDouble(), meanYear);
    if (t0 != null && t1 != null) {
      final a = Offset(xAt(firstYear), yAt(t0));
      final b = Offset(xAt(lastYear), yAt(t1));
      final paint = Paint()
        ..color = line
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke;
      final length = (b - a).distance;
      if (length > 0) {
        final dir = (b - a) / length;
        for (var d = 0.0; d < length; d += 9) {
          canvas.drawLine(
            a + dir * d,
            a + dir * math.min(d + 5, length),
            paint,
          );
        }
      }
    }
  }

  @override
  bool shouldRepaint(ClimateChartPainter old) =>
      !identical(old.series, series) ||
      old.metric != metric ||
      old.trend != trend ||
      old.bar != bar ||
      old.line != line ||
      old.grid != grid ||
      old.label != label;
}

/// The trend in words, from the server's numbers. Three honest cases: a clear
/// trend, one that can't be told apart from year-to-year variation (which is
/// not "no change"), and too few complete years to fit one.
class _TrendCard extends StatelessWidget {
  final ClimateMetric metric;
  final ClimatePeriod period;
  final ClimateTrend? trend;
  final int minYears;
  const _TrendCard({
    required this.metric,
    required this.period,
    required this.trend,
    required this.minYears,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final tr_ = trend;
    final String headline;
    final String body;
    final Map<String, Object?> args;
    if (tr_ == null || !tr_.hasSlope) {
      headline = 'No trend';
      body =
          "Not enough complete years to fit a trend: at least {min} are needed, and there are {n}.";
      args = {'min': minYears, 'n': tr_?.n ?? 0};
    } else {
      headline = 'Trend';
      final se = tr_.stderrPerDecade;
      args = {
        'slope': formatClimate(tr_.slopePerDecade!, metric, slope: true),
        'se': se == null
            ? ''
            : formatClimate(se, metric, slope: true).replaceFirst('+', ''),
        'n': tr_.n,
        'from': tr_.firstYear ?? '',
        'to': tr_.lastYear ?? '',
        'mean': formatClimate(tr_.mean!, metric),
      };
      body = tr_.significant95
          ? 'Change of {slope} per decade (± {se}) over {n} complete years, {from}–{to}. The average is {mean}. A change this size is clear of year-to-year variation at the 95% level.'
          : "Change of {slope} per decade (± {se}) over {n} complete years, {from}–{to}. The average is {mean}. This can't be told apart from year-to-year variation. That does not mean nothing has changed.";
    }
    return AppCard(
      color: t.surfaceContainerLow,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const IconDisc(Icons.trending_up, solid: true),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  tr(context, headline),
                  style: AppText.headlineSm.copyWith(
                    color: t.ink,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            tr(context, body, args),
            style: AppText.bodyMd.copyWith(color: t.ink),
          ),
        ],
      ),
    );
  }
}

/// Every year's figure as text: the chart's data for anyone who can't see it.
class _YearList extends StatelessWidget {
  final ClimateMetric metric;
  final List<YearValue> series;
  const _YearList({required this.metric, required this.series});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    // ListTile paints on the nearest Material; the page's gradient is a plain
    // DecoratedBox, so give it its own.
    return Material(
      color: Colors.transparent,
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: EdgeInsets.zero,
          childrenPadding: EdgeInsets.zero,
          title: Text(
            tr(context, 'Show every year'),
            style: AppText.labelMd.copyWith(
              color: t.primary,
              fontWeight: FontWeight.w600,
            ),
          ),
          children: [
            for (final p in series.reversed)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    SizedBox(
                      width: 64,
                      child: Text(
                        '${p.year}',
                        style: AppText.citationMono.copyWith(
                          color: t.onSurfaceVariant,
                        ),
                      ),
                    ),
                    Expanded(
                      child: Text(
                        p.value == null
                            ? tr(context, 'Missing days — left out')
                            : formatClimate(p.value!, metric),
                        style: AppText.bodyMd.copyWith(
                          color: p.value == null ? t.inkMuted : t.ink,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// The source line, credit link, "computed by WeatherGPT" note and licence and
/// terms links — on every state of the page.
class _Source extends StatelessWidget {
  final ClimateData data;
  const _Source({required this.data});

  Future<void> _open(String url) async {
    final uri = Uri.tryParse(url);
    if (uri == null || uri.scheme != 'https') return;
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      // No browser to open it: the link is just text then.
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: t.tint,
            borderRadius: BorderRadius.circular(AppRadius.xl),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline, size: 16, color: t.primary),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  '${tr(context, data.changesNote)} ${tr(context, data.calendarNote)}',
                  style: AppText.bodySm.copyWith(color: t.inkMuted),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpace.sm),
        // The source line, exactly as the server sends it (CLM-5's wording).
        Text(
          data.label,
          style: AppText.citationMono.copyWith(color: t.onSurfaceVariant),
        ),
        Wrap(
          spacing: AppSpace.md,
          children: [
            _Link(data.creditText, () => _open(data.creditUrl)),
            _Link('Licence', () => _open(data.licenceUrl)),
            _Link('Terms of use', () => _open(data.termsUrl)),
          ],
        ),
      ],
    );
  }
}

class _Link extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _Link(this.label, this.onTap);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: kMinInteractiveDimension),
      child: InkWell(
        onTap: onTap,
        child: Align(
          widthFactor: 1,
          alignment: Alignment.centerLeft,
          child: Text(
            tr(context, label),
            style: AppText.labelMd.copyWith(
              color: t.primary,
              decoration: TextDecoration.underline,
            ),
          ),
        ),
      ),
    );
  }
}
