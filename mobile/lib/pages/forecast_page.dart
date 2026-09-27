// Forecast — web/src/pages/ForecastPage.tsx: region header, the outlook
// accordion, the provenance card and the live /ask composer. The web page's
// hourly chart/strip and 10-day list are static samples (no endpoint serves
// an hourly series or a structured 10-day breakdown), so this page shows
// what GET /facts does serve — today, tonight and tomorrow — and leaves
// longer ranges to /ask ("5-day forecast for …"), which narrates them.
import 'package:flutter/material.dart';

import '../components/ask_answer.dart';
import '../components/common.dart';
import '../components/composer.dart';
import '../facts_client.dart';
import '../format.dart';
import '../state/ask_controller.dart';
import '../state/ui_prefs.dart';
import '../state/weather_store.dart';
import '../theme.dart';

class ForecastPage extends StatefulWidget {
  const ForecastPage({super.key});

  @override
  State<ForecastPage> createState() => _ForecastPageState();
}

class _ForecastPageState extends State<ForecastPage> {
  final AskController _ask = AskController();
  final TextEditingController _query = TextEditingController();
  final Set<String> _expanded = {'today'};

  @override
  void dispose() {
    _ask.dispose();
    _query.dispose();
    super.dispose();
  }

  void _submit(String text) {
    final prefs = UiPrefs.read(context);
    _ask.ask(text, lang: prefs.lang, city: prefs.city, persona: prefs.persona);
  }

  void _toggle(String key) => setState(() => _expanded.contains(key) ? _expanded.remove(key) : _expanded.add(key));

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final weather = WeatherStore.of(context);
    final city = prefs.cityInfo;

    return RefreshIndicator(
      onRefresh: weather.refresh,
      child: ListView(
        padding: const EdgeInsets.all(AppSpace.gutter),
        children: [
          const PageHeader(
            title: 'Forecast',
            subtitle: 'Today, tonight and tomorrow, read straight from the forecast feed — never generated.',
          ),
          const SizedBox(height: AppSpace.lg),
          SurfaceCard(
            radius: AppRadius.xl,
            child: Row(children: [
              const _PulseDot(),
              const SizedBox(width: AppSpace.sm),
              Expanded(child: Text('${city.name}, ${city.region}', style: AppText.headlineSm)),
              if (weather.today?.hasData == true) LiveBadge(live: weather.today!.isLive),
            ]),
          ),
          const SizedBox(height: AppSpace.lg),
          Text('Outlook', style: AppText.headlineMd),
          const SizedBox(height: AppSpace.md),
          ..._periods(weather),
          const SizedBox(height: AppSpace.lg),
          _ProvenanceCard(weather: weather),
          const SizedBox(height: AppSpace.lg),
          ListenableBuilder(
            listenable: _ask,
            builder: (context, _) => SurfaceCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const RuleLabel(icon: Icons.bolt, text: 'Live — answers come from /ask'),
                if (_ask.asked != null) ...[
                  const SizedBox(height: AppSpace.sm),
                  AskAnswer(
                    asked: _ask.asked,
                    loading: _ask.loading,
                    outcome: _ask.outcome,
                    error: _ask.error,
                    detail: true,
                    playbackLang: _ask.lang,
                  ),
                ],
                const SizedBox(height: AppSpace.sm),
                SuggestionChips(
                  enabled: !_ask.loading,
                  suggestions: [
                    Suggestion('📅', '5-day forecast for ${city.name}'),
                    Suggestion('🌙', 'Will it rain tonight in ${city.name}?'),
                  ],
                  onPick: (text) {
                    _query.text = text;
                    _submit(text);
                  },
                ),
                const SizedBox(height: AppSpace.sm),
                AskComposer(
                  controller: _query,
                  loading: _ask.loading,
                  lang: prefs.lang,
                  showMic: false,
                  hint: "Ask for a forecast, e.g. '5-day forecast for ${city.name}'",
                  onSubmit: _submit,
                ),
                const SizedBox(height: 6),
                const Padding(padding: EdgeInsets.symmetric(horizontal: 4), child: CityHintRow()),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _periods(WeatherStore weather) {
    if (weather.error != null) {
      return [
        ErrorPanel(
          icon: Icons.wifi_off,
          title: 'Forecast unavailable',
          message: weather.error!.message,
          onRetry: weather.refresh,
        ),
      ];
    }
    if (weather.today == null) return [const LoadingPanel('Loading the forecast…')];

    final rows = [
      ('today', 'Today', weather.today, 0, false),
      ('tonight', 'Tonight', weather.tonight, 0, true),
      ('tomorrow', 'Tomorrow', weather.tomorrow, 1, false),
    ];
    return [
      for (final (key, label, result, offset, night) in rows) ...[
        _PeriodCard(
          label: label,
          result: result,
          dayOffset: offset,
          night: night,
          expanded: _expanded.contains(key),
          onToggle: () => _toggle(key),
        ),
        const SizedBox(height: 10),
      ],
    ];
  }
}

/// `w-2.5 h-2.5 rounded-full bg-secondary-container animate-pulse`.
class _PulseDot extends StatefulWidget {
  const _PulseDot();

  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(seconds: 1));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween<double>(begin: 1, end: 0.5).animate(CurvedAnimation(parent: _c, curve: Curves.easeInOut)),
      child: Container(
        width: 10,
        height: 10,
        decoration: const BoxDecoration(color: AppColors.secondaryContainer, shape: BoxShape.circle),
      ),
    );
  }
}

/// One outlook accordion row (ForecastPage.tsx's synoptic accordion).
class _PeriodCard extends StatelessWidget {
  final String label;
  final FactsResult? result;
  final int dayOffset;
  final bool night;
  final bool expanded;
  final VoidCallback onToggle;

  const _PeriodCard({
    required this.label,
    required this.result,
    required this.dayOffset,
    required this.night,
    required this.expanded,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final r = result;
    final style = conditionStyle(r?.condition, night: night);
    final high = r?.number('high_c');
    final low = r?.number('low_c');
    final rain = r?.number('rain_probability_pct');
    final hasData = r?.hasData == true;

    return SurfaceCard(
      radius: AppRadius.xl,
      onTap: hasData ? onToggle : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Icon(style.icon, size: 28, color: style.iconColor),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('$label, ${istDayMonth(r?.issued, fallbackOffsetDays: dayOffset)}', style: AppText.headlineSm),
              Text(
                hasData ? sentenceCase(r!.conditionLabel) : (r?.message ?? 'No forecast for this period.'),
                style: AppText.bodySm.copyWith(color: AppColors.onSurfaceVariant),
              ),
            ]),
          ),
          if (hasData) ...[
            // Tonight's high/low are the whole day's — show only the low.
            Text.rich(
              TextSpan(children: [
                if (!night && high != null) TextSpan(text: '${prefs.temp(high)}°', style: AppText.headlineSm),
                if (low != null)
                  TextSpan(
                    text: night ? 'Low ${prefs.temp(low)}°' : ' / ${prefs.temp(low)}°',
                    style: night ? AppText.headlineSm : AppText.bodySm.copyWith(color: AppColors.outline),
                  ),
              ]),
            ),
            const SizedBox(width: AppSpace.sm),
            Icon(expanded ? Icons.expand_less : Icons.expand_more, size: 20, color: AppColors.onSurfaceVariant),
          ],
        ]),
        if (hasData && expanded) ...[
          const SizedBox(height: AppSpace.sm),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.surfaceContainerLow.withValues(alpha: 0.6),
              borderRadius: BorderRadius.circular(AppRadius.lg),
              border: const Border(top: BorderSide(color: AppColors.surfaceContainer)),
            ),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                child: _Stat('Precip prob', rain == null ? '—' : '${rain.round()}%', color: AppColors.primary),
              ),
              Expanded(
                child: night
                    ? _Stat('Overnight low', low == null ? '—' : prefs.tempLabel(low))
                    : _Stat('High / Low',
                        '${high == null ? '—' : prefs.temp(high)}° / ${low == null ? '—' : prefs.temp(low)}°'),
              ),
              Expanded(child: _Stat('Period', night ? 'Night' : 'Day')),
            ]),
          ),
        ],
      ]),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _Stat(this.label, this.value, {this.color = AppColors.onSurface});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label.toUpperCase(), style: AppText.citationMono.copyWith(color: AppColors.outline)),
      const SizedBox(height: 2),
      Text(value, style: AppText.headlineSm.copyWith(color: color)),
    ]);
  }
}

class _ProvenanceCard extends StatelessWidget {
  final WeatherStore weather;
  const _ProvenanceCard({required this.weather});

  @override
  Widget build(BuildContext context) {
    final r = weather.today;
    final source = r?.source;
    return SurfaceCard(
      radius: AppRadius.xl,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.verified_outlined, size: 20, color: AppColors.secondary),
          const SizedBox(width: AppSpace.sm),
          Expanded(child: Text('Forecast Provenance', style: AppText.headlineSm)),
          if (r?.hasData == true) LiveBadge(live: r!.isLive),
        ]),
        const SizedBox(height: AppSpace.sm),
        Text(
          source == null
              ? 'Every figure on this page is read directly from the forecast feed — never generated by the language model.'
              : 'As served by $source. Every figure above is read directly from that response — '
                  'never generated by the language model.',
          style: AppText.bodySm.copyWith(color: AppColors.onSurfaceVariant),
        ),
      ]),
    );
  }
}
