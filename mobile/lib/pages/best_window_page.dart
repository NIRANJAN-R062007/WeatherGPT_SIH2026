// Best Time & What-if — opened from the drawer's "Best Time & What-if" item
// (plan.md §8 Phase 9, WIE-14): a best-window card (the longest suitable run
// of hours today or tomorrow) and a what-if comparison view (two named times
// of day, the lower-rain-chance one named), both from the Weather
// Intelligence Engine's deterministic rules (intelligence_client.dart;
// web/src/pages/BestWindowPage.tsx). Nothing here is narrated by an LLM —
// every figure is read straight from the engine's result (plan.md §2
// principle 7), the same discipline as the Alerts and Forecast pages.
import 'package:flutter/material.dart';

import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../intelligence_client.dart';
import '../persona_theme.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import '../i18n.dart';

typedef BestWindowFetcher = Future<Map<String, dynamic>> Function({
  required String city,
  required String day,
  String activity,
});
typedef ScenarioFetcher = Future<Map<String, dynamic>> Function({
  required String city,
  required String day,
  required List<String> times,
  String activity,
});

final List<String> kHourOptions = [for (var h = 0; h < 24; h++) '${h.toString().padLeft(2, '0')}:00'];

Future<void> openBestWindow(BuildContext context) {
  return Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const BestWindowPage()));
}

class BestWindowPage extends StatefulWidget {
  /// Where the window and scenario come from; tests pass stubs.
  final BestWindowFetcher windowFetcher;
  final ScenarioFetcher scenarioFetcher;
  const BestWindowPage({
    super.key,
    this.windowFetcher = fetchBestWindow,
    this.scenarioFetcher = fetchScenario,
  });

  @override
  State<BestWindowPage> createState() => _BestWindowPageState();
}

class _BestWindowPageState extends State<BestWindowPage> {
  String _day = 'today';
  String? _city;
  bool _loading = false;
  Map<String, dynamic>? _window;
  IntelligenceError? _windowError;
  int _windowRequestId = 0;

  String _timeA = '09:00';
  String _timeB = '17:00';
  bool _scenarioLoading = false;
  Map<String, dynamic>? _scenario;
  IntelligenceError? _scenarioError;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final city = UiPrefs.of(context).city;
    if (city != _city) _loadWindow(city, _day);
  }

  void _loadWindow(String city, String day) {
    if (city != _city || day != _day) {
      _scenario = null;
      _scenarioError = null;
    }
    _city = city;
    _day = day;
    _loading = true;
    _windowError = null;
    _fetchWindow(++_windowRequestId, city, day);
  }

  Future<void> _fetchWindow(int id, String city, String day) async {
    try {
      final data = await widget.windowFetcher(city: city, day: day);
      if (!mounted || id != _windowRequestId) return;
      setState(() {
        _window = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || id != _windowRequestId) return;
      setState(() {
        _windowError = e is IntelligenceError
            ? e
            : IntelligenceError(IntelligenceErrorKind.network, 'Something went wrong finding the best window.');
        _window = null;
        _loading = false;
      });
    }
  }

  Future<void> _compare() async {
    final city = _city;
    if (city == null) return;
    setState(() {
      _scenarioLoading = true;
      _scenarioError = null;
    });
    try {
      final data = await widget.scenarioFetcher(city: city, day: _day, times: [_timeA, _timeB]);
      if (!mounted) return;
      setState(() {
        _scenario = data;
        _scenarioLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _scenarioError = e is IntelligenceError
            ? e
            : IntelligenceError(IntelligenceErrorKind.network, 'Something went wrong comparing those times.');
        _scenario = null;
        _scenarioLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final city = tr(context, prefs.cityInfo.name);

    return SubPageScaffold(
      body: PageFrame(
        onRefresh: () async {
          final c = UiPrefs.read(context).city;
          _loadWindow(c, _day);
        },
        children: [
          const PageHeader(
            title: 'Best Time & What-if',
            subtitle: 'When conditions are most suitable to be outdoors, and how two times of day compare — '
                'decided by rules, not the language model.',
          ),
          const SizedBox(height: AppSpace.md),
          _DaySwitch(
            value: _day,
            onChanged: (d) => setState(() => _loadWindow(UiPrefs.read(context).city, d)),
          ),
          const SizedBox(height: AppSpace.md),
          const SectionTitle('Best window'),
          const SizedBox(height: AppSpace.sm),
          _windowBody(city),
          const SizedBox(height: AppSpace.lg),
          const SectionTitle("What if I go at a different time?"),
          const SizedBox(height: AppSpace.sm),
          _WhatIfView(
            timeA: _timeA,
            timeB: _timeB,
            onTimeA: (v) => setState(() => _timeA = v),
            onTimeB: (v) => setState(() => _timeB = v),
            onCompare: _compare,
            loading: _scenarioLoading,
            data: _scenario,
            error: _scenarioError,
          ),
          const SizedBox(height: AppSpace.lg),
          _InfoNote(city: city),
        ],
      ),
    );
  }

  Widget _windowBody(String city) {
    if (_loading) return const LoadingPanel('Finding the best window…');
    if (_windowError != null) {
      return ErrorPanel(
        icon: Icons.wifi_off,
        title: 'Best window unavailable',
        message: _windowError!.message,
        messageArgs: _windowError!.args,
        onRetry: () => _loadWindow(_city ?? city, _day),
      );
    }
    final data = _window;
    if (data == null) return const SizedBox.shrink();
    final status = data['status'] as String?;
    if (status == 'unavailable') {
      return _NeutralCard(
        icon: Icons.help_outline,
        title: 'No hourly forecast to check',
        body: tr(
          context,
          "There's no hourly forecast for {city} {day} right now — this can't be read as a suitable or unsuitable window.",
          {'city': city, 'day': tr(context, _day)},
        ),
      );
    }
    if (status == 'no_suitable_window') {
      return _NeutralCard(
        icon: Icons.block,
        title: 'No suitable window',
        body: tr(
          context,
          "Every hour {day} in {city} was checked against rain under 20%, 20–32°C and wind under 25 km/h — none passed. That's a real result, not a guess.",
          {'city': city, 'day': tr(context, _day)},
        ),
      );
    }
    final w = data['window'] as Map<String, dynamic>?;
    if (w == null) return const SizedBox.shrink();
    final provenance = data['provenance'] as Map<String, dynamic>?;
    return _WindowCard(window: w, city: city, source: provenance?['source'] as String?);
  }
}

class _DaySwitch extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  const _DaySwitch({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    Widget tab(String v, String label) {
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
      child: Row(children: [tab('today', 'Today'), const SizedBox(width: 4), tab('tomorrow', 'Tomorrow')]),
    );
  }
}

class _NeutralCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String body;
  const _NeutralCard({required this.icon, required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return AppCard(
      color: t.surfaceContainerLow,
      borderColor: t.outlineVariant,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconDisc(icon, color: t.onSurfaceVariant, background: t.surfaceContainerHigh),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  tr(context, title),
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text(tr(context, body), style: AppText.bodyMd.copyWith(color: t.onSurface)),
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
                tr(context, label),
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

class _WindowCard extends StatelessWidget {
  final Map<String, dynamic> window;
  final String city;
  final String? source;
  const _WindowCard({required this.window, required this.city, this.source});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return AppCard(
      wash: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const IconDisc(Icons.check, solid: true, size: 36),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${window['start_local']} – ${window['end_local']}',
                      style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 4),
                    Wrap(spacing: 6, runSpacing: 4, children: [
                      TagChip(city, icon: Icons.location_on_outlined),
                      const TagChip('more suitable for being outdoors'),
                    ]),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.md),
          Row(children: [
            Expanded(child: _Figure(Icons.thermostat, 'Avg temp', '${window['avg_temp_c']}°C')),
            Expanded(child: _Figure(Icons.umbrella_outlined, 'Max rain chance', '${window['max_rain_probability_pct']}%')),
            Expanded(child: _Figure(Icons.air, 'Max wind', '${window['max_wind_kmh']} km/h')),
          ]),
          if (source != null) ...[
            const SizedBox(height: AppSpace.md),
            Divider(height: 1, color: t.outlineVariant.withValues(alpha: 0.4)),
            const SizedBox(height: AppSpace.xs),
            Text('${tr(context, 'source')}: $source', style: AppText.citationMono.copyWith(color: t.onSurfaceVariant)),
          ],
        ],
      ),
    );
  }
}

class _HourPicker extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  const _HourPicker({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: t.card,
        border: Border.all(color: t.cardBorder),
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value, // not dense: 48 dp, Android's minimum touch target
          style: AppText.labelMd.copyWith(color: t.ink),
          dropdownColor: t.card,
          items: [for (final h in kHourOptions) DropdownMenuItem(value: h, child: Text(h))],
          onChanged: (v) {
            if (v != null) onChanged(v);
          },
        ),
      ),
    );
  }
}

class _ScenarioHourCard extends StatelessWidget {
  final String time;
  final Map<String, dynamic>? result;
  final bool better;
  const _ScenarioHourCard({required this.time, required this.result, required this.better});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final available = result?['available'] == true;
    return AppCard(
      borderColor: better ? t.primary : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: 6, runSpacing: 4, children: [
            Text(time, style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700)),
            if (better) const TagChip('lower rain chance', tone: ChipTone.primary),
          ]),
          const SizedBox(height: AppSpace.sm),
          if (!available)
            Text(tr(context, 'Not available in this forecast.'), style: AppText.bodySm.copyWith(color: t.inkMuted))
          else
            Row(children: [
              Expanded(child: _Figure(Icons.thermostat, 'Temp', '${result!['temp_c']}°C')),
              Expanded(child: _Figure(Icons.umbrella_outlined, 'Rain', '${result!['rain_probability_pct']}%')),
              Expanded(child: _Figure(Icons.air, 'Wind', '${result!['wind_kmh']} km/h')),
            ]),
        ],
      ),
    );
  }
}

class _WhatIfView extends StatelessWidget {
  final String timeA;
  final String timeB;
  final ValueChanged<String> onTimeA;
  final ValueChanged<String> onTimeB;
  final VoidCallback onCompare;
  final bool loading;
  final Map<String, dynamic>? data;
  final IntelligenceError? error;
  const _WhatIfView({
    required this.timeA,
    required this.timeB,
    required this.onTimeA,
    required this.onTimeB,
    required this.onCompare,
    required this.loading,
    required this.data,
    required this.error,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final hours = (data?['hours'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final byTime = {for (final h in hours) h['time'] as String: h};
    final betterTime = data?['better_time'] as String?;
    final status = data?['status'] as String?;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 8,
          runSpacing: 8,
          children: [
            _HourPicker(value: timeA, onChanged: onTimeA),
            Text(tr(context, 'vs'), style: AppText.bodySm.copyWith(color: t.inkMuted)),
            _HourPicker(value: timeB, onChanged: onTimeB),
            PillButton(icon: Icons.compare_arrows, label: 'Compare', onPressed: onCompare),
          ],
        ),
        const SizedBox(height: AppSpace.sm),
        if (loading) const LoadingPanel('Comparing…'),
        if (error != null)
          ErrorPanel(
            icon: Icons.wifi_off,
            title: 'Comparison unavailable',
            message: error!.message,
            messageArgs: error!.args,
            onRetry: onCompare,
          ),
        if (status == 'unavailable')
          _NeutralCard(
            icon: Icons.help_outline,
            title: 'No hourly forecast to check',
            body: "There's no hourly forecast right now to compare against.",
          ),
        if (status == 'ok')
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: _ScenarioHourCard(time: timeA, result: byTime[timeA], better: betterTime == timeA)),
              const SizedBox(width: AppSpace.sm),
              Expanded(child: _ScenarioHourCard(time: timeB, result: byTime[timeB], better: betterTime == timeB)),
            ],
          ),
      ],
    );
  }
}

class _InfoNote extends StatelessWidget {
  final String city;
  const _InfoNote({required this.city});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(color: t.tint, borderRadius: BorderRadius.circular(AppRadius.xl)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline, size: 16, color: t.primary),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              tr(
                context,
                'A window is "more suitable", never "safe" — rain under 20%, 20–32°C and wind under 25 km/h, checked against the hourly forecast, the same rules every time regardless of persona. A colour-code warning for {city} always comes from Alerts, not from here.',
                {'city': city},
              ),
              style: AppText.bodySm.copyWith(color: t.inkMuted),
            ),
          ),
        ],
      ),
    );
  }
}
