// Home — the pics/ persona mockups' Home: a persona greeting ("Good
// morning, Farmer!"), the current-conditions card, today's rain so far and
// daylight, four shortcut tiles, the outlook strip, the persona's
// illustrated panel and its Quick Actions. Every figure is live from the
// backend (WeatherStore): /facts for the card and the rain, /forecast/daily
// for the sun times and the strip's five days. A backend without
// /forecast/daily gets today / tonight / tomorrow from /facts in the strip,
// and the 5-Day tile asks Chat instead. When the backend can't be reached,
// the saved figures show under a banner saying when they were saved.
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
import '../i18n.dart';

/// "Good afternoon, Farmer!" — the persona's role, per the mockups.
String _greeting(BuildContext context, DateTime ist, String role) {
  final greeting = ist.hour < 12
      ? 'Good morning, {role}!'
      : ist.hour < 17
      ? 'Good afternoon, {role}!'
      : 'Good evening, {role}!';
  return tr(context, greeting, {'role': tr(context, role)});
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
    final prefs = UiPrefs.of(context);
    final city = tr(context, prefs.cityInfo.name);
    final persona = prefs.personaInfo;

    return PageFrame(
      onRefresh: weather.refresh,
      footer: SceneryFooter.none,
      children: [
        _Greeting(text: _greeting(context, _now, persona.role), lead: tr(context, persona.homeLead)),
        if (weather.savedAt case final savedAt?) ...[
          const SizedBox(height: AppSpace.md),
          SavedDataBanner(
            message: "Couldn't reach the weather service. These figures were saved at {time}.",
            messageArgs: {'time': savedTimeLabel(savedAt, langOf(context))},
            onRetry: weather.refresh,
          ),
        ],
        const SizedBox(height: AppSpace.md),
        _NowCard(weather: weather),
        _TodayCards(weather: weather, now: _now),
        const SizedBox(height: 12),
        _QuickTiles(
          tiles: [
            (Icons.today, 'Today', () => nav.go(AppPage.forecast)),
            (
              Icons.date_range,
              '5-Day',
              weather.hasDaily
                  ? () => nav.go(AppPage.forecast)
                  : () => nav.ask(tr(context, '5-day forecast for {city}', {'city': city})),
            ),
            (Icons.warning_rounded, 'Alerts', () => nav.go(AppPage.alerts)),
            (Icons.chat_rounded, 'Chat', () => nav.go(AppPage.chat)),
          ],
        ),
        const SizedBox(height: AppSpace.lg),
        SectionTitle('Forecast', action: 'See all', onAction: () => nav.go(AppPage.forecast)),
        const SizedBox(height: AppSpace.sm),
        _OutlookStrip(weather: weather),
        const SizedBox(height: AppSpace.md),
        const _ScenePanel(),
        const SizedBox(height: AppSpace.lg),
        const SectionTitle('Quick Actions'),
        const SizedBox(height: AppSpace.sm),
        for (final q in persona.quickActions) ...[
          ActionRow(
            icon: q.icon,
            title: tr(context, q.label ?? q.template, {'city': city}),
            onTap: () => nav.ask(tr(context, q.template, {'city': city})),
          ),
          const SizedBox(height: AppSpace.sm),
        ],
      ],
    );
  }
}

/// The four shortcut tiles under the now card (Today, 5-Day, Alerts, Chat).
class _QuickTiles extends StatelessWidget {
  final List<(IconData, String, VoidCallback)> tiles;
  const _QuickTiles({required this.tiles});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Row(
      children: [
        for (final (i, (icon, label, onTap)) in tiles.indexed) ...[
          if (i > 0) const SizedBox(width: 10),
          Expanded(
            child: AppCard(
              padding: const EdgeInsets.symmetric(vertical: 12),
              onTap: onTap,
              child: Column(
                children: [
                  Icon(icon, size: 26, color: t.primary),
                  const SizedBox(height: 6),
                  Text(
                    tr(context, label),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}

/// The persona's illustrated landscape panel (farmland, harbour, airport,
/// skyline) between the forecast and Quick Actions.
class _ScenePanel extends StatelessWidget {
  const _ScenePanel();

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return ExcludeSemantics(
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AppRadius.card),
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [t.skyTop, t.skyBottom],
            ),
          ),
          child: const SizedBox(height: 132, child: PersonaScenery(SceneSlot.panel)),
        ),
      ),
    );
  }
}

class _Greeting extends StatelessWidget {
  final String text;
  final String lead;
  const _Greeting({required this.text, required this.lead});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final persona = UiPrefs.of(context).personaInfo;
    return Row(
      children: [
        Tooltip(
          message: tr(context, 'Change persona'),
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: () => openPersonaPicker(context),
            child: IconDisc(persona.icon, size: 52, solid: true),
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
              Text(lead, style: AppText.bodySm.copyWith(color: t.inkMuted)),
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
        messageArgs: weather.error!.args,
        onRetry: weather.refresh,
      );
    } else if (c == null) {
      body = LoadingPanel(
        tr(context, 'Loading live conditions for {city}…', {'city': tr(context, prefs.cityInfo.name)}),
      );
    } else if (!c.hasData) {
      body = Text(
        c.message ?? tr(context, 'No current conditions for this city right now.'),
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
                      tr(context, 'Feels like {temp}', {'temp': prefs.tempLabel(feels)}),
                      style: AppText.bodySm.copyWith(color: t.inkMuted),
                    ),
                ],
              ),
            ),
            Container(width: 1, height: 72, margin: const EdgeInsets.symmetric(horizontal: 10), color: t.cardBorder),
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
            // A saved copy was live once, not now.
            c.savedAt == null ? LiveBadge(live: c.isLive) : const LiveBadge(live: false, notLiveText: 'SAVED'),
            const SizedBox(width: AppSpace.sm),
            if (c.issued != null)
              Expanded(
                child: Text(
                  tr(context, 'Updated {time}', {'time': istTime(c.issued)}),
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
            tr(context, label),
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

/// Rain so far today (/facts' `rain_so_far`) and today's daylight
/// (/forecast/daily's first day), side by side; either alone fills the row.
class _TodayCards extends StatelessWidget {
  final WeatherStore weather;
  final DateTime now;
  const _TodayCards({required this.weather, required this.now});

  @override
  Widget build(BuildContext context) {
    final rain = weather.error == null ? weather.current?.rainSoFar : null;
    final today = weather.hasDaily ? weather.daily!.entries.first : null;
    final rise = istMinuteOfDay(today?.sunrise);
    final set = istMinuteOfDay(today?.sunset);
    final cards = [
      if (rain != null) _RainCard(rain, saved: weather.current?.savedAt != null),
      if (rise != null && set != null && set > rise)
        _DaylightCard(sunrise: today!.sunrise!, sunset: today.sunset!, rise: rise, set: set, now: now),
    ];
    if (cards.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (final (i, card) in cards.indexed) ...[
              if (i > 0) const SizedBox(width: 10),
              Expanded(child: card),
            ],
          ],
        ),
      ),
    );
  }
}

/// A small card's icon + title row.
class _CardTitle extends StatelessWidget {
  final IconData icon;
  final String title;
  final Widget? trailing;
  const _CardTitle(this.icon, this.title, {this.trailing});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Row(
      children: [
        Icon(icon, size: 16, color: t.primary),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            tr(context, title),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
          ),
        ),
        ?trailing,
      ],
    );
  }
}

/// Millimetres since local midnight with the IMD category, or the last 24
/// hours' total when the backend had no hourly history to sum.
class _RainCard extends StatelessWidget {
  final Figures rain;
  final bool saved;
  const _RainCard(this.rain, {required this.saved});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final sinceMidnight = rain.number('rain_so_far_mm');
    final mm = sinceMidnight ?? rain.number('rain_last_24h_mm');
    final category = rainCategoryLabel(rain.text('rain_category'));
    final muted = AppText.bodySm.copyWith(color: t.inkMuted);
    return AppCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CardTitle(
            Icons.water_drop_outlined,
            'Rain so far',
            trailing: saved
                ? const LiveBadge(live: false, notLiveText: 'SAVED')
                : (rain.isLive ? null : const LiveBadge(live: false)),
          ),
          const SizedBox(height: 8),
          Text(mm == null ? '—' : millimetres(mm), style: AppText.headlineSm.copyWith(color: t.ink)),
          if (category != null) Text(tr(context, category), style: muted),
          Text(tr(context, sinceMidnight != null ? 'Since midnight' : 'In the last 24 hours'), style: muted),
        ],
      ),
    );
  }
}

/// Day length with a bar for how much of it has passed, and the sunrise and
/// sunset times. The bar reads [now]'s IST clock time against the two.
class _DaylightCard extends StatelessWidget {
  final String sunrise;
  final String sunset;
  final int rise;
  final int set;
  final DateTime now;
  const _DaylightCard({
    required this.sunrise,
    required this.sunset,
    required this.rise,
    required this.set,
    required this.now,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final minute = now.hour * 60 + now.minute;
    final passed = ((minute - rise) / (set - rise)).clamp(0.0, 1.0);
    final muted = AppText.bodySm.copyWith(color: t.inkMuted);
    Widget time(IconData icon, String label, String iso) => Semantics(
      label: '${tr(context, label)} ${istClock(iso)}',
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: t.primary),
          const SizedBox(width: 2),
          Text(istClock(iso), style: muted),
        ],
      ),
    );

    return AppCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _CardTitle(Icons.wb_twilight, 'Daylight'),
          const SizedBox(height: 8),
          Text(
            hoursMinutes(Duration(minutes: set - rise), langOf(context)),
            style: AppText.headlineSm.copyWith(color: t.ink),
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(value: passed, minHeight: 6, color: t.primary, backgroundColor: t.tint),
          ),
          const SizedBox(height: 6),
          // Sunset drops to its own line rather than overflow a narrow card.
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            spacing: 8,
            runSpacing: 2,
            children: [time(Icons.arrow_upward, 'Sunrise', sunrise), time(Icons.arrow_downward, 'Sunset', sunset)],
          ),
        ],
      ),
    );
  }
}

/// Five days from /forecast/daily in one card, like the mockup's day
/// columns; today / tonight / tomorrow from /facts on an older backend.
class _OutlookStrip extends StatelessWidget {
  final WeatherStore weather;
  const _OutlookStrip({required this.weather});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    if (weather.hasDaily) {
      return AppCard(
        wash: true,
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: AppSpace.sm),
        child: Row(
          children: [
            for (final day in weather.daily!.entries.take(5)) Expanded(child: _DailyCell(day: day)),
          ],
        ),
      );
    }
    if (weather.dailyPending) return const LoadingPanel('Loading the outlook…');
    if (weather.error != null) {
      return AppCard(
        child: Text(
          tr(context, 'The outlook will appear once the weather service answers.'),
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

class _DailyCell extends StatelessWidget {
  final ForecastDay day;
  const _DailyCell({required this.day});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final high = day.number('high_c');
    final low = day.number('low_c');
    return Column(
      children: [
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            forecastDayName(day.label, day.date, langOf(context)),
            maxLines: 1,
            style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
          ),
        ),
        const SizedBox(height: 8),
        WeatherGlyph(day.condition, size: 30),
        const SizedBox(height: 8),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text.rich(
            TextSpan(
              children: [
                if (high != null)
                  TextSpan(
                    text: '${prefs.temp(high)}° ',
                    style: TextStyle(color: t.ink, fontWeight: FontWeight.w600),
                  ),
                if (low != null) TextSpan(text: '${prefs.temp(low)}°'),
              ],
            ),
            maxLines: 1,
            style: AppText.bodySm.copyWith(color: t.inkMuted),
          ),
        ),
      ],
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
          tr(context, label),
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
                if (low != null)
                  TextSpan(text: night ? tr(context, 'Low {temp}°', {'temp': prefs.temp(low)}) : '${prefs.temp(low)}°'),
              ],
            ),
            style: muted,
          ),
      ],
    );
  }
}
