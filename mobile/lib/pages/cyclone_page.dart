// Cyclone map — opened from the drawer's "Cyclone map" item (plan.md §8
// Phase 5, CYC-5): tropical cyclones near India from GDACS, drawn on a
// schematic map of the Indian Ocean region, with a card per storm below it
// (cyclones_client.dart; services/orchestrator/gdacs.py). The map is the
// picture and the cards are the same facts as text, so nothing depends on
// colour or on seeing the map.
//
// GDACS is not IMD, so "GDACS" is on the map itself and the attribution and
// not-an-official-alert disclaimer sit next to it. The alert colour is
// GDACS's own level, passed through — the app never grades a storm (plan.md
// §2 principle 4). A failed fetch is "not available", never "no cyclones"
// (principle 3): only a live, complete, empty answer says there are none.
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../cyclones_client.dart';
import '../format.dart';
import '../i18n.dart';
import '../persona_theme.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import '../warning_colors.dart';

Future<void> openCycloneMap(BuildContext context) {
  return Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const CyclonePage()));
}

class CyclonePage extends StatefulWidget {
  /// Where cyclones come from; tests pass a stub.
  final CyclonesFetcher fetcher;
  const CyclonePage({super.key, this.fetcher = fetchCyclones});

  @override
  State<CyclonePage> createState() => _CyclonePageState();
}

class _CyclonePageState extends State<CyclonePage> {
  bool _loading = true;
  CyclonesData? _data;
  CyclonesError? _error;
  int _requestId = 0;

  @override
  void initState() {
    super.initState();
    _fetch(++_requestId);
  }

  Future<void> _fetch(int id) async {
    try {
      final data = await widget.fetcher();
      if (!mounted || id != _requestId) return;
      setState(() {
        _data = data;
        _error = null;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || id != _requestId) return;
      setState(() {
        _error = e is CyclonesError
            ? e
            : CyclonesError(CyclonesErrorKind.network, 'Something went wrong talking to the cyclone service.');
        _data = null;
        _loading = false;
      });
    }
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    await _fetch(++_requestId);
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    return SubPageScaffold(
      body: PageFrame(
        onRefresh: _reload,
        children: [
          const PageHeader(
            title: 'Cyclone map',
            subtitle: 'Tropical cyclones near India in the last two weeks, from GDACS.',
          ),
          const SizedBox(height: AppSpace.lg),
          if (_loading)
            const LoadingPanel('Fetching the cyclone data…')
          else if (_error != null)
            ErrorPanel(
              icon: Icons.wifi_off,
              title: 'Cyclone map unavailable',
              message: _error!.message,
              messageArgs: _error!.args,
              onRetry: _reload,
            )
          else if (data != null && data.unavailable)
            _Unavailable(data)
          else if (data != null) ..._ready(context, data),
        ],
      ),
    );
  }

  List<Widget> _ready(BuildContext context, CyclonesData data) {
    final events = data.events!;
    return [
      if (!data.isLive) ...[
        _SnapshotBanner(retrievedAt: data.retrievedAt),
        const SizedBox(height: AppSpace.sm),
      ],
      if (events.isEmpty)
        _NoCyclones(data)
      else ...[
        _MapCard(data: data, events: events),
        const SizedBox(height: AppSpace.md),
        const _Legend(),
        const SizedBox(height: AppSpace.lg),
        const SectionTitle('Cyclones'),
        const SizedBox(height: AppSpace.sm),
        for (final e in events) ...[_EventCard(event: e, live: data.isLive), const SizedBox(height: AppSpace.sm)],
      ],
      const SizedBox(height: AppSpace.sm),
      _Attribution(data: data),
    ];
  }
}

/// The fetch failed: no verdict, and explicitly not "no cyclones".
class _Unavailable extends StatelessWidget {
  final CyclonesData data;
  const _Unavailable(this.data);

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
                      tr(context, 'No cyclone data'),
                      style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpace.sm),
              Text(
                tr(context, "The cyclone data isn't available right now — this can't be read as \"no cyclones\"."),
                style: AppText.bodyMd.copyWith(color: t.ink),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpace.md),
        _Attribution(data: data),
      ],
    );
  }
}

/// A live, complete, empty answer is the only one that says there are none;
/// a snapshot or a cut-short search says what it can't confirm instead.
class _NoCyclones extends StatelessWidget {
  final CyclonesData data;
  const _NoCyclones(this.data);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final confirmed = data.noCyclonesConfirmed;
    return AppCard(
      color: t.surfaceContainerLow,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconDisc(confirmed ? Icons.check_circle_outline : Icons.help_outline),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  tr(context, confirmed ? 'No cyclones near India' : 'No cyclones in this data'),
                  style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            tr(
              context,
              confirmed
                  ? 'GDACS lists no tropical cyclone near India in the last {days} days.'
                  : "This copy of the GDACS data lists no cyclone near India, but it isn't a live check — don't read it as all clear.",
              {'days': data.windowDays},
            ),
            style: AppText.bodyMd.copyWith(color: t.ink),
          ),
        ],
      ),
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
      decoration: BoxDecoration(color: AppColors.tertiaryFixed, borderRadius: BorderRadius.circular(AppRadius.lg)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 2),
            child: Icon(Icons.history, size: 14, color: AppColors.onTertiaryFixed),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              tr(context, 'Snapshot taken {time} — not live data.', {'time': istTimestamp(retrievedAt)}),
              style: AppText.bodySm.copyWith(color: AppColors.onTertiaryFixed),
            ),
          ),
        ],
      ),
    );
  }
}

/// The attribution GDACS asks for, the terms link, and the not-an-official-
/// alert disclaimer — shown on every state of the page.
class _Attribution extends StatelessWidget {
  final CyclonesData data;
  const _Attribution({required this.data});

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
          decoration: BoxDecoration(color: t.tint, borderRadius: BorderRadius.circular(AppRadius.xl)),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline, size: 16, color: t.primary),
              const SizedBox(width: 6),
              Expanded(
                child: Text(tr(context, data.disclaimer), style: AppText.bodySm.copyWith(color: t.inkMuted)),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpace.sm),
        Text(tr(context, data.attribution), style: AppText.citationMono.copyWith(color: t.onSurfaceVariant)),
        Wrap(
          spacing: AppSpace.md,
          children: [
            _LinkText('gdacs.org', () => _open(data.sourceUrl)),
            if (data.termsUrl.isNotEmpty) _LinkText('Terms of use', () => _open(data.termsUrl)),
          ],
        ),
      ],
    );
  }
}

class _LinkText extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _LinkText(this.label, this.onTap);

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
            style: AppText.labelMd.copyWith(color: t.primary, decoration: TextDecoration.underline),
          ),
        ),
      ),
    );
  }
}

String _levelWord(BuildContext context, String level) {
  final known = {'green': 'Green alert', 'orange': 'Orange alert', 'red': 'Red alert'}[level.toLowerCase()];
  return known != null ? tr(context, known) : level;
}

/// What the map's lines and fills mean.
class _Legend extends StatelessWidget {
  const _Legend();

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    Widget item(Widget mark, String text) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        const SizedBox(width: 6),
        Flexible(child: Text(tr(context, text), style: AppText.bodySm.copyWith(color: t.inkMuted))),
      ],
    );
    Widget line({bool dashed = false}) => SizedBox(
      width: 22,
      height: 10,
      child: CustomPaint(painter: _LegendLine(t.ink, dashed)),
    );
    return Wrap(
      spacing: AppSpace.md,
      runSpacing: AppSpace.xs,
      children: [
        item(line(), 'Track so far'),
        item(line(dashed: true), 'Forecast track'),
        item(
          Container(
            width: 14,
            height: 14,
            decoration: BoxDecoration(color: t.ink.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(3)),
          ),
          'Forecast uncertainty',
        ),
      ],
    );
  }
}

class _LegendLine extends CustomPainter {
  final Color color;
  final bool dashed;
  const _LegendLine(this.color, this.dashed);

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = color
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    _strokeSegment(canvas, Offset(0, size.height / 2), Offset(size.width, size.height / 2), p, dashed);
  }

  @override
  bool shouldRepaint(_LegendLine old) => old.color != color || old.dashed != dashed;
}

void _strokeSegment(Canvas canvas, Offset a, Offset b, Paint paint, bool dashed) {
  if (!dashed) {
    canvas.drawLine(a, b, paint);
    return;
  }
  const dash = 6.0;
  const gap = 4.0;
  final length = (b - a).distance;
  if (length == 0) return;
  final dir = (b - a) / length;
  for (var d = 0.0; d < length; d += dash + gap) {
    canvas.drawLine(a + dir * d, a + dir * math.min(d + dash, length), paint);
  }
}

class _MapCard extends StatelessWidget {
  final CyclonesData data;
  final List<CycloneEvent> events;
  const _MapCard({required this.data, required this.events});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final (lonMin, lonMax, latMin, latMax) = data.area;
    final names = events.map((e) => '${e.name}, ${_levelWord(context, e.alertLevel)}').join('; ');
    final label = tr(context, 'Map of tropical cyclones near India: {events}. The same details are listed below.', {
      'events': names,
    });
    final cities = UiPrefs.of(context).cities;
    return AppCard(
      padding: const EdgeInsets.all(AppSpace.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpace.xs, AppSpace.xs, AppSpace.xs, AppSpace.sm),
            child: Wrap(
              spacing: 8,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                // "GDACS" on the map itself (plan.md CYC-5), not only in the footer.
                const TagChip('GDACS', icon: Icons.public, tone: ChipTone.primary),
                LiveBadge(live: data.isLive),
              ],
            ),
          ),
          Semantics(
            label: label,
            image: true,
            excludeSemantics: true,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.xl),
              child: AspectRatio(
                aspectRatio: (lonMax - lonMin) / (latMax - latMin),
                child: CustomPaint(
                  painter: CycloneMapPainter(
                    events: events,
                    cities: [
                      for (final c in cities) (lon: c.lon, lat: c.lat, name: tr(context, c.name)),
                    ],
                    lonMin: lonMin,
                    lonMax: lonMax,
                    latMin: latMin,
                    latMax: latMax,
                    sea: t.surfaceContainerLow,
                    grid: t.outlineVariant,
                    ink: t.ink,
                    muted: t.inkMuted,
                  ),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpace.xs, AppSpace.sm, AppSpace.xs, AppSpace.xs),
            child: Text(
              tr(context, 'Schematic map without coastlines. Dots are the cities this app covers.'),
              style: AppText.bodySm.copyWith(color: t.inkMuted),
            ),
          ),
        ],
      ),
    );
  }
}

/// Draws the events on an equirectangular grid of [lonMin]–[lonMax] ×
/// [latMin]–[latMax]. No basemap: a coastline needs data the app doesn't
/// carry, so cities give the orientation. Colours are GDACS's alert levels.
class CycloneMapPainter extends CustomPainter {
  final List<CycloneEvent> events;
  final List<({double lon, double lat, String name})> cities;
  final double lonMin, lonMax, latMin, latMax;
  final Color sea, grid, ink, muted;

  const CycloneMapPainter({
    required this.events,
    required this.cities,
    required this.lonMin,
    required this.lonMax,
    required this.latMin,
    required this.latMax,
    required this.sea,
    required this.grid,
    required this.ink,
    required this.muted,
  });

  Offset _at(Size size, double lon, double lat) => Offset(
    (lon - lonMin) / (lonMax - lonMin) * size.width,
    (latMax - lat) / (latMax - latMin) * size.height,
  );

  Path _ring(Size size, List<LonLat> ring) {
    final path = Path();
    for (var i = 0; i < ring.length; i++) {
      final p = _at(size, ring[i].lon, ring[i].lat);
      i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
    }
    return path..close();
  }

  void _label(Canvas canvas, String text, Offset at, Color color, {double size = 10, bool bold = false}) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(fontSize: size, color: color, fontWeight: bold ? FontWeight.w700 : FontWeight.w500),
      ),
      textDirection: TextDirection.ltr,
      maxLines: 1,
    )..layout();
    tp.paint(canvas, at);
  }

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = sea);

    // Graticule every 5°, labelled every 10°.
    final gridPaint = Paint()
      ..color = grid.withValues(alpha: 0.5)
      ..strokeWidth = 0.7;
    for (var lon = (lonMin / 5).ceil() * 5.0; lon <= lonMax; lon += 5) {
      final x = _at(size, lon, latMin).dx;
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
      if (lon % 10 == 0) _label(canvas, '${lon.toInt()}°E', Offset(x + 2, size.height - 13), muted, size: 9);
    }
    for (var lat = (latMin / 5).ceil() * 5.0; lat <= latMax; lat += 5) {
      final y = _at(size, lonMin, lat).dy;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
      if (lat % 10 == 0 && lat != latMin) _label(canvas, '${lat.toInt()}°N', Offset(2, y + 1), muted, size: 9);
    }

    for (final c in cities) {
      final p = _at(size, c.lon, c.lat);
      canvas.drawCircle(p, 2.5, Paint()..color = muted);
      _label(canvas, c.name, p + const Offset(4, -5), muted, size: 8);
    }

    // Biggest picture first: wind areas, then the cone, then the track on top.
    for (final e in events) {
      final color = warningColor(e.alertLevel.toLowerCase());
      for (final area in e.windAreas) {
        for (final ring in area.rings) {
          canvas.drawPath(_ring(size, ring), Paint()..color = color.withValues(alpha: 0.07));
        }
      }
      for (final ring in e.cone) {
        final path = _ring(size, ring);
        canvas.drawPath(path, Paint()..color = ink.withValues(alpha: 0.14));
        canvas.drawPath(
          path,
          Paint()
            ..color = ink.withValues(alpha: 0.35)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 0.8,
        );
      }
    }
    for (final e in events) {
      final color = warningColor(e.alertLevel.toLowerCase());
      for (final s in e.segments) {
        final paint = Paint()
          ..color = s.isForecast ? ink.withValues(alpha: 0.75) : color
          ..strokeWidth = s.isForecast ? 1.8 : 2.6
          ..strokeCap = StrokeCap.round
          ..style = PaintingStyle.stroke;
        for (var i = 0; i + 1 < s.points.length; i++) {
          _strokeSegment(
            canvas,
            _at(size, s.points[i].lon, s.points[i].lat),
            _at(size, s.points[i + 1].lon, s.points[i + 1].lat),
            paint,
            s.isForecast,
          );
        }
      }
      final lon = e.lon, lat = e.lat;
      if (lon != null && lat != null) {
        final p = _at(size, lon, lat);
        canvas.drawCircle(p, 8, Paint()..color = color.withValues(alpha: 0.25));
        canvas.drawCircle(p, 4.5, Paint()..color = color);
        canvas.drawCircle(
          p,
          4.5,
          Paint()
            ..color = Colors.white
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.2,
        );
        _label(canvas, e.name, p + const Offset(9, -6), ink, size: 11, bold: true);
      }
    }
  }

  @override
  bool shouldRepaint(CycloneMapPainter old) =>
      !identical(old.events, events) ||
      old.cities.length != cities.length ||
      old.sea != sea ||
      old.ink != ink ||
      old.grid != grid ||
      old.muted != muted;
}

class _EventCard extends StatelessWidget {
  final CycloneEvent event;
  final bool live;
  const _EventCard({required this.event, required this.live});

  Future<void> _openReport() async {
    final uri = Uri.tryParse(event.reportUrl ?? '');
    if (uri == null || uri.scheme != 'https' || uri.host != 'www.gdacs.org') return;
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      // No browser to open it with: the card still has every figure.
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final color = warningColor(event.alertLevel.toLowerCase());
    final episode = event.episodeAlertLevel;
    final rows = <(String, String)>[
      if (event.severityText != null) ('Strength', event.severityText!),
      if (episode != null && episode.toLowerCase() != event.alertLevel.toLowerCase())
        ('Current episode', _levelWord(context, episode)),
      if (event.fromDate != null) ('Since', istTimestamp(event.fromDate)),
      if (event.dateModified != null) ('Updated', istTimestamp(event.dateModified)),
      if (event.sourceAgency != null) ('Bulletin from', event.sourceAgency!),
    ];
    return AppCard(
      padding: const EdgeInsets.all(AppSpace.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 14,
                height: 14,
                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  event.title,
                  style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.xs),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              TagChip(_levelWord(context, event.alertLevel), icon: Icons.warning_amber_rounded, tone: ChipTone.primary),
              if (event.isCurrent) const TagChip('Current'),
              const TagChip('GDACS'),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          for (final (label, value) in rows)
            Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: '${tr(context, label)}: ',
                      style: AppText.bodySm.copyWith(color: t.inkMuted),
                    ),
                    TextSpan(text: value, style: AppText.bodyMd.copyWith(color: t.ink)),
                  ],
                ),
              ),
            ),
          if (event.reportUrl != null && Uri.tryParse(event.reportUrl!)?.host == 'www.gdacs.org')
            _LinkText('Open the GDACS report', _openReport),
        ],
      ),
    );
  }
}
