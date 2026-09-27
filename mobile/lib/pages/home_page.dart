// Home — web/src/pages/HomePage.tsx: the current-weather hero (with its
// time-of-day/condition gradient), the feature tiles, and the WeatherGPT
// Copilot composer. Unlike web/'s hero, every figure here is live from
// GET /facts; the web hero's sunrise/sunset panel and "rain so far today"
// tile are left out because /facts doesn't carry them.
import 'dart:async';

import 'package:flutter/material.dart';

import '../components/app_shell.dart';
import '../components/ask_answer.dart';
import '../components/common.dart';
import '../components/composer.dart';
import '../facts_client.dart';
import '../format.dart';
import '../state/ask_controller.dart';
import '../state/ui_prefs.dart';
import '../state/weather_store.dart';
import '../theme.dart';

const String _quickQuery = 'Will it rain today?';

// Only tints the hero (dawn/day/dusk/night), exactly as HomePage.tsx does
// with the same fixed IST times — /facts has no sunrise/sunset field.
const int _sunriseMin = 6 * 60 + 32;
const int _sunsetMin = 18 * 60 + 14;
const int _transitionWindowMin = 40;

enum _Mood { dawn, day, dusk, night }

const Map<_Mood, Color> _moodTint = {
  _Mood.dawn: AppColors.tertiaryFixedDim,
  _Mood.day: AppColors.surfaceContainerLow,
  _Mood.dusk: AppColors.tertiaryContainer,
  _Mood.night: AppColors.inverseSurface,
};

_Mood _moodAt(DateTime ist) {
  final now = ist.hour * 60 + ist.minute;
  if ((now - _sunriseMin).abs() <= _transitionWindowMin) return _Mood.dawn;
  if ((now - _sunsetMin).abs() <= _transitionWindowMin) return _Mood.dusk;
  if (now > _sunriseMin && now < _sunsetMin) return _Mood.day;
  return _Mood.night;
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with SingleTickerProviderStateMixin {
  final AskController _ask = AskController();
  final TextEditingController _query = TextEditingController();

  // `.animate-gradient-drift`: 18 s ease-in-out there and back.
  late final AnimationController _drift =
      AnimationController(vsync: this, duration: const Duration(seconds: 9));
  late final Animation<double> _driftCurve = CurvedAnimation(parent: _drift, curve: Curves.easeInOut);
  late Timer _clock;
  DateTime _now = nowIst();

  @override
  void initState() {
    super.initState();
    _clock = Timer.periodic(const Duration(minutes: 1), (_) => setState(() => _now = nowIst()));
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Ambient only — honour the OS "remove animations" setting.
    if (MediaQuery.disableAnimationsOf(context)) {
      _drift.stop();
    } else if (!_drift.isAnimating) {
      _drift.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _clock.cancel();
    _drift.dispose();
    _ask.dispose();
    _query.dispose();
    super.dispose();
  }

  void _submit(String text) {
    final prefs = UiPrefs.read(context);
    _ask.ask(text, lang: prefs.lang, city: prefs.city, persona: prefs.persona);
  }

  @override
  Widget build(BuildContext context) {
    final weather = WeatherStore.of(context);
    return RefreshIndicator(
      onRefresh: weather.refresh,
      child: ListView(
        padding: const EdgeInsets.all(AppSpace.gutter),
        children: [
          _Hero(weather: weather, mood: _moodAt(_now), drift: _driftCurve),
          const SizedBox(height: AppSpace.lg),
          const _FeatureTiles(),
          const SizedBox(height: AppSpace.lg),
          ListenableBuilder(
            listenable: _ask,
            builder: (context, _) => _CopilotCard(ask: _ask, query: _query, onSubmit: _submit),
          ),
        ],
      ),
    );
  }
}

class _Hero extends StatelessWidget {
  final WeatherStore weather;
  final _Mood mood;
  final Animation<double> drift;
  const _Hero({required this.weather, required this.mood, required this.drift});

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final current = weather.current;
    final accent = conditionStyle(current?.condition).accent;
    final tint = _moodTint[mood]!;

    final Widget content;
    if (weather.error != null) {
      content = ErrorPanel(
        icon: Icons.wifi_off,
        title: 'Live conditions unavailable',
        message: weather.error!.message,
        onRetry: weather.refresh,
      );
    } else if (current == null) {
      content = LoadingPanel('Loading live conditions for ${prefs.cityInfo.name}…');
    } else if (!current.hasData) {
      content = _NoData(current.message ?? 'No current conditions for this city right now.');
    } else {
      content = _HeroBody(weather: weather, accent: accent, tint: tint);
    }

    // `linear-gradient(135deg, #f1f3ff 0%, <mood>33 55%, <accent>4d 100%)` on
    // a 200% background drifting left to right, as in HomePage.tsx.
    return AnimatedBuilder(
      animation: drift,
      builder: (context, child) {
        final t = drift.value;
        return DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppRadius.x2l),
            boxShadow: AppShadows.sm,
            gradient: LinearGradient(
              begin: Alignment(-1 - 2 * t, -2),
              end: Alignment(3 - 2 * t, 2),
              colors: [
                AppColors.surfaceContainerLow,
                tint.withValues(alpha: 0x33 / 255),
                accent.withValues(alpha: 0x4d / 255),
              ],
              stops: const [0, 0.55, 1],
            ),
          ),
          child: child,
        );
      },
      child: Padding(padding: const EdgeInsets.all(AppSpace.md), child: content),
    );
  }
}

class _NoData extends StatelessWidget {
  final String message;
  const _NoData(this.message);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColors.surfaceContainer,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Row(children: [
        const Icon(Icons.info_outline, size: 18, color: AppColors.onSurfaceVariant),
        const SizedBox(width: AppSpace.sm),
        Expanded(child: Text(message, style: AppText.bodyMd)),
      ]),
    );
  }
}

class _HeroBody extends StatelessWidget {
  final WeatherStore weather;
  final Color accent;
  final Color tint;
  const _HeroBody({required this.weather, required this.accent, required this.tint});

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final c = weather.current!;
    final style = conditionStyle(c.condition);
    final temp = c.number('temp_c');
    final feels = c.number('feels_like_c');
    final humidity = c.number('humidity_pct');
    final wind = c.number('wind_kmh');
    final windDir = c.text('wind_dir');
    final uv = c.number('uv_index');
    final uvBand = c.text('uv_band');
    final rain = weather.today?.number('rain_probability_pct');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Temperature block: `linear-gradient(135deg, <accent>4d, <mood>1a 60%, transparent)`.
        Container(
          padding: const EdgeInsets.all(AppSpace.md),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppRadius.xl),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                accent.withValues(alpha: 0x4d / 255),
                tint.withValues(alpha: 0x1a / 255),
                Colors.transparent,
              ],
              stops: const [0, 0.6, 1],
            ),
          ),
          child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(temp == null ? '—' : '${prefs.temp(temp)}°', style: AppText.metricDisplay),
                const SizedBox(width: 4),
                Text(prefs.unitSymbol, style: AppText.headlineSm.copyWith(color: AppColors.onSurfaceVariant)),
              ],
            ),
            const SizedBox(width: AppSpace.md),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Icon(style.icon, size: 26, color: AppColors.primary),
                  const SizedBox(width: AppSpace.sm),
                  Expanded(
                    child: Text(
                      sentenceCase(c.conditionLabel),
                      style: AppText.headlineSm.copyWith(color: AppColors.primary),
                    ),
                  ),
                ]),
                if (feels != null) ...[
                  const SizedBox(height: AppSpace.xs),
                  Text.rich(
                    TextSpan(children: [
                      const TextSpan(text: 'Feels like '),
                      TextSpan(
                        text: prefs.tempLabel(feels),
                        style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.onSurface),
                      ),
                    ]),
                    style: AppText.bodyMd.copyWith(color: AppColors.onSurfaceVariant),
                  ),
                ],
              ]),
            ),
          ]),
        ),
        const SizedBox(height: AppSpace.sm),
        Wrap(spacing: AppSpace.sm, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
          TagChip(c.cityName ?? prefs.cityInfo.name, icon: Icons.location_on_outlined),
          LiveBadge(live: c.isLive),
          if (c.issued != null)
            Text(
              'Updated ${istTime(c.issued)}',
              style: AppText.citationMono.copyWith(color: AppColors.onSurfaceVariant),
            ),
        ]),
        const SizedBox(height: AppSpace.md),
        Row(children: [
          Expanded(
            child: _MetricTile(
              label: 'Humidity',
              icon: Icons.water_drop_outlined,
              value: humidity == null ? '—' : '${humidity.round()}%',
            ),
          ),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: _MetricTile(
              label: 'Wind',
              icon: Icons.air,
              value: wind == null ? '—' : '${wind.round()} km/h${windDir == null ? '' : ' $windDir'}',
              secondary: true,
            ),
          ),
        ]),
        const SizedBox(height: AppSpace.sm),
        Row(children: [
          Expanded(
            child: _MetricTile(
              label: 'Rain chance today',
              icon: Icons.umbrella_outlined,
              value: rain == null ? '—' : '${rain.round()}%',
            ),
          ),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: _MetricTile(
              label: 'UV index',
              icon: Icons.wb_sunny_outlined,
              value: uv == null ? '—' : '${uv.round()}${uvBand == null ? '' : ' · ${uvBand.replaceAll('_', ' ')}'}',
            ),
          ),
        ]),
        const SizedBox(height: AppSpace.md),
        const MonoLabel('Outlook'),
        const SizedBox(height: AppSpace.sm),
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: _DayChip(label: 'Today', result: weather.today, highlight: true)),
          const SizedBox(width: AppSpace.sm),
          Expanded(child: _DayChip(label: 'Tonight', result: weather.tonight, night: true)),
          const SizedBox(width: AppSpace.sm),
          Expanded(child: _DayChip(label: 'Tomorrow', result: weather.tomorrow)),
        ]),
      ],
    );
  }
}

/// `p-2.5 rounded-xl bg-primary-container text-on-primary-container`.
class _MetricTile extends StatelessWidget {
  final String label;
  final IconData icon;
  final String value;
  final bool secondary;
  const _MetricTile({required this.label, required this.icon, required this.value, this.secondary = false});

  @override
  Widget build(BuildContext context) {
    final fg = secondary ? AppColors.onSecondaryContainer : AppColors.onPrimaryContainer;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: secondary ? AppColors.secondaryContainer : AppColors.primaryContainer,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(
          label.toUpperCase(),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppText.citationMono.copyWith(color: fg.withValues(alpha: 0.8)),
        ),
        const SizedBox(height: 4),
        Row(children: [
          Icon(icon, size: 18, color: fg),
          const SizedBox(width: 4),
          Expanded(
            child: Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.headlineSm.copyWith(color: fg),
            ),
          ),
        ]),
      ]),
    );
  }
}

/// One outlook chip — the first is the solid primary "Today" chip.
class _DayChip extends StatelessWidget {
  final String label;
  final FactsResult? result;
  final bool highlight;
  final bool night;
  const _DayChip({required this.label, required this.result, this.highlight = false, this.night = false});

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final r = result;
    final style = conditionStyle(r?.condition, night: night);
    final fg = highlight ? AppColors.onPrimary : AppColors.onSurface;
    final muted = highlight ? AppColors.onPrimary.withValues(alpha: 0.7) : AppColors.onSurfaceVariant;
    final high = r?.number('high_c');
    final low = r?.number('low_c');
    final rain = r?.number('rain_probability_pct');

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: AppSpace.sm),
      decoration: BoxDecoration(
        color: highlight ? AppColors.primary : AppColors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        boxShadow: AppShadows.sm,
      ),
      child: Column(children: [
        Text(
          label.toUpperCase(),
          style: AppText.chipMono.copyWith(color: highlight ? fg : muted, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 4),
        Icon(style.icon, size: 22, color: highlight ? AppColors.secondaryFixed : style.iconColor),
        const SizedBox(height: 4),
        if (r == null || !r.hasData)
          Text('—', style: AppText.labelMd.copyWith(color: muted))
        else
          // Tonight's high/low are the whole day's, so only the overnight low.
          Text.rich(
            TextSpan(children: [
              if (!night && high != null) TextSpan(text: '${prefs.temp(high)}° '),
              if (low != null)
                TextSpan(
                  text: '${night ? 'Low ' : ''}${prefs.temp(low)}°',
                  style: TextStyle(color: muted, fontSize: 11),
                ),
            ]),
            style: AppText.labelMd.copyWith(color: fg, fontWeight: FontWeight.w600),
          ),
        const SizedBox(height: 4),
        Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.umbrella_outlined, size: 12, color: highlight ? fg : AppColors.primary),
          const SizedBox(width: 2),
          Text(
            rain == null ? '—' : '${rain.round()}%',
            style: AppText.chipMono.copyWith(color: highlight ? fg : muted),
          ),
        ]),
      ]),
    );
  }
}

class _FeatureTiles extends StatelessWidget {
  const _FeatureTiles();

  @override
  Widget build(BuildContext context) {
    final nav = ShellNav.of(context);
    return IntrinsicHeight(
      child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Expanded(
          child: _FeatureTile(
            icon: Icons.mic_none,
            tag: 'AI audio',
            title: 'Voice Assistant',
            body: 'Ask in हिंदी, தமிழ், తెలుగు, मराठी or English',
            onTap: () => nav.go(AppPage.chat),
          ),
        ),
        const SizedBox(width: AppSpace.md),
        Expanded(
          child: _FeatureTile(
            icon: Icons.translate,
            tag: '5 languages',
            title: 'Multilingual Answers',
            body: 'Narration translated, numbers stay grounded',
            secondary: true,
            onTap: () => nav.go(AppPage.settings),
          ),
        ),
      ]),
    );
  }
}

class _FeatureTile extends StatelessWidget {
  final IconData icon;
  final String tag;
  final String title;
  final String body;
  final bool secondary;
  final VoidCallback onTap;
  const _FeatureTile({
    required this.icon,
    required this.tag,
    required this.title,
    required this.body,
    required this.onTap,
    this.secondary = false,
  });

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: secondary ? AppColors.secondaryContainer : AppColors.primaryContainer,
              borderRadius: BorderRadius.circular(AppRadius.xl),
            ),
            child: Icon(
              icon,
              size: 20,
              color: secondary ? AppColors.onSecondaryContainer : AppColors.onPrimaryContainer,
            ),
          ),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: Text(
              tag.toUpperCase(),
              textAlign: TextAlign.right,
              style: AppText.chipMono.copyWith(
                color: secondary ? AppColors.secondary : AppColors.primary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ]),
        const SizedBox(height: 12),
        Text(title, style: AppText.labelMd.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 2),
        Text(body, style: AppText.bodySm.copyWith(fontSize: 11, height: 1.3, color: AppColors.onSurfaceVariant)),
      ]),
    );
  }
}

class _CopilotCard extends StatelessWidget {
  final AskController ask;
  final TextEditingController query;
  final ValueChanged<String> onSubmit;
  const _CopilotCard({required this.ask, required this.query, required this.onSubmit});

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    return SurfaceCard(
      padding: const EdgeInsets.all(AppSpace.lg),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Container(
            width: 28,
            height: 28,
            decoration: const BoxDecoration(color: AppColors.primary, shape: BoxShape.circle),
            child: const Icon(Icons.smart_toy_outlined, size: 16, color: AppColors.onPrimary),
          ),
          const SizedBox(width: AppSpace.sm),
          Text('WeatherGPT Copilot', style: AppText.headlineSm.copyWith(fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: AppSpace.md),
        const MonoLabel('Quick situational inquiries'),
        const SizedBox(height: 6),
        QuickQueryButton(
          text: _quickQuery,
          enabled: !ask.loading,
          onTap: () {
            query.text = _quickQuery;
            onSubmit(_quickQuery);
          },
        ),
        const SizedBox(height: AppSpace.sm),
        AskComposer(
          inset: true,
          controller: query,
          loading: ask.loading,
          lang: prefs.lang,
          onSubmit: onSubmit,
        ),
        const SizedBox(height: AppSpace.sm),
        const CityHintRow(showLang: false),
        if (ask.asked != null) ...[
          const SizedBox(height: AppSpace.md),
          AskAnswer(
            asked: ask.asked,
            loading: ask.loading,
            outcome: ask.outcome,
            error: ask.error,
            playbackLang: ask.lang,
          ),
        ],
      ]),
    );
  }
}
