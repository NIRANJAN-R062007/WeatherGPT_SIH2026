// Home — the pics/ mockup's Home: a greeting with the persona avatar, the
// current-conditions card, the outlook strip and Quick Questions. Every
// figure is live from GET /facts (WeatherStore). /facts serves today,
// tonight and tomorrow only, so the strip shows those three rather than the
// mockup's five days; longer ranges are one tap away as a Quick Question,
// which Chat answers through /ask.
import 'dart:async';

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
import 'persona_page.dart';

String _greeting(DateTime ist) {
  if (ist.hour < 12) return 'Good morning!';
  if (ist.hour < 17) return 'Good afternoon!';
  return 'Good evening!';
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late Timer _clock;
  DateTime _now = nowIst();

  @override
  void initState() {
    super.initState();
    _clock = Timer.periodic(const Duration(minutes: 1), (_) => setState(() => _now = nowIst()));
  }

  @override
  void dispose() {
    _clock.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final weather = WeatherStore.of(context);
    final nav = ShellNav.of(context);
    final city = UiPrefs.of(context).cityInfo.name;
    final questions = [
      (Icons.umbrella_outlined, 'Will it rain today?', 'Will it rain today in $city?'),
      (Icons.nights_stay_outlined, 'What should I expect this evening?', 'What is the weather tonight in $city?'),
      (Icons.calendar_month_outlined, '5-day forecast', '5-day forecast for $city'),
    ];

    return PageFrame(
      onRefresh: weather.refresh,
      footer: SceneryFooter.soft,
      children: [
        _Greeting(text: _greeting(_now)),
        const SizedBox(height: AppSpace.md),
        _NowCard(weather: weather),
        const SizedBox(height: AppSpace.lg),
        SectionTitle('Forecast', action: 'See all', onAction: () => nav.go(AppPage.forecast)),
        const SizedBox(height: AppSpace.sm),
        _OutlookStrip(weather: weather),
        const SizedBox(height: AppSpace.lg),
        const SectionTitle('Quick Questions'),
        const SizedBox(height: AppSpace.sm),
        for (final (icon, label, question) in questions) ...[
          ActionRow(icon: icon, title: label, onTap: () => nav.ask(question)),
          const SizedBox(height: AppSpace.sm),
        ],
      ],
    );
  }
}

class _Greeting extends StatelessWidget {
  final String text;
  const _Greeting({required this.text});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final persona = UiPrefs.of(context).personaInfo;
    return Row(
      children: [
        Tooltip(
          message: 'Change persona',
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: () => openPersonaPicker(context),
            child: IconDisc(persona.icon, size: 44, solid: true),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                text,
                style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
              ),
              Text(
                "Here's the latest weather for your city.",
                style: AppText.bodySm.copyWith(color: t.inkMuted),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// The big current-conditions card.
class _NowCard extends StatelessWidget {
  final WeatherStore weather;
  const _NowCard({required this.weather});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final c = weather.current;

    final Widget body;
    if (weather.error != null) {
      body = ErrorPanel(
        icon: Icons.wifi_off,
        title: 'Live conditions unavailable',
        message: weather.error!.message,
        onRetry: weather.refresh,
      );
    } else if (c == null) {
      body = LoadingPanel('Loading live conditions for ${prefs.cityInfo.name}…');
    } else if (!c.hasData) {
      body = Text(
        c.message ?? 'No current conditions for this city right now.',
        style: AppText.bodyMd.copyWith(color: t.inkMuted),
      );
    } else {
      body = _NowBody(c: c, rain: weather.today?.number('rain_probability_pct'));
    }
    return AppCard(wash: true, padding: const EdgeInsets.all(AppSpace.md), child: body);
  }
}

class _NowBody extends StatelessWidget {
  final FactsResult c;
  final num? rain;
  const _NowBody({required this.c, required this.rain});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final temp = c.number('temp_c');
    final feels = c.number('feels_like_c');
    final humidity = c.number('humidity_pct');
    final wind = c.number('wind_kmh');
    final night = nowIst().hour >= 19 || nowIst().hour < 6;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            WeatherGlyph(c.condition, night: night, size: 64),
            const SizedBox(width: 12),
            Expanded(
              flex: 5,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(
                      temp == null ? '—' : prefs.tempLabel(temp),
                      style: AppText.headlineXl.copyWith(fontSize: 34, color: t.ink, height: 1.1),
                    ),
                  ),
                  Text(
                    sentenceCase(c.conditionLabel),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.bodyMd.copyWith(color: t.inkMuted),
                  ),
                  if (feels != null)
                    Text(
                      'Feels like ${prefs.tempLabel(feels)}',
                      style: AppText.bodySm.copyWith(color: t.inkMuted),
                    ),
                ],
              ),
            ),
            Container(
              width: 1,
              height: 72,
              margin: const EdgeInsets.symmetric(horizontal: 10),
              color: t.cardBorder,
            ),
            Expanded(
              flex: 5,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _Stat(Icons.water_drop_outlined, 'Humidity', humidity == null ? '—' : '${humidity.round()}%'),
                  const SizedBox(height: 6),
                  _Stat(Icons.air, 'Wind', wind == null ? '—' : '${wind.round()} km/h'),
                  const SizedBox(height: 6),
                  _Stat(Icons.umbrella_outlined, 'Rain', rain == null ? '—' : '${rain!.round()}%'),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            LiveBadge(live: c.isLive),
            const SizedBox(width: AppSpace.sm),
            if (c.issued != null)
              Expanded(
                child: Text(
                  'Updated ${istTime(c.issued)}',
                  overflow: TextOverflow.ellipsis,
                  style: AppText.citationMono.copyWith(color: t.inkMuted),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _Stat(this.icon, this.label, this.value);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Row(
      children: [
        Icon(icon, size: 15, color: t.inkMuted),
        const SizedBox(width: 5),
        Expanded(
          child: Text(
            label,
            overflow: TextOverflow.ellipsis,
            style: AppText.bodySm.copyWith(color: t.inkMuted),
          ),
        ),
        Text(
          value,
          style: AppText.bodySm.copyWith(color: t.ink, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

/// Today / Tonight / Tomorrow in one card, like the mockup's day columns.
class _OutlookStrip extends StatelessWidget {
  final WeatherStore weather;
  const _OutlookStrip({required this.weather});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    if (weather.error != null) {
      return AppCard(
        child: Text(
          'The outlook will appear once the weather service answers.',
          style: AppText.bodySm.copyWith(color: t.inkMuted),
        ),
      );
    }
    if (weather.today == null) return const LoadingPanel('Loading the outlook…');
    return AppCard(
      wash: true,
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: AppSpace.sm),
      child: Row(
        children: [
          Expanded(
            child: _DayCell(label: 'Today', result: weather.today),
          ),
          Expanded(
            child: _DayCell(label: 'Tonight', result: weather.tonight, night: true),
          ),
          Expanded(
            child: _DayCell(label: 'Tomorrow', result: weather.tomorrow),
          ),
        ],
      ),
    );
  }
}

class _DayCell extends StatelessWidget {
  final String label;
  final FactsResult? result;
  final bool night;
  const _DayCell({required this.label, required this.result, this.night = false});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final r = result;
    final high = r?.number('high_c');
    final low = r?.number('low_c');
    final muted = AppText.bodySm.copyWith(color: t.inkMuted);
    return Column(
      children: [
        Text(
          label,
          style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        WeatherGlyph(r?.condition, night: night, size: 34),
        const SizedBox(height: 8),
        if (r == null || !r.hasData)
          Text('—', style: muted)
        else
          // Tonight's high/low are the whole day's, so only the overnight low.
          Text.rich(
            TextSpan(
              children: [
                if (!night && high != null)
                  TextSpan(
                    text: '${prefs.temp(high)}°  ',
                    style: TextStyle(color: t.ink, fontWeight: FontWeight.w600),
                  ),
                if (low != null) TextSpan(text: night ? 'Low ${prefs.temp(low)}°' : '${prefs.temp(low)}°'),
              ],
            ),
            style: muted,
          ),
      ],
    );
  }
}
