// Airport weather — opened from the drawer's "Airport weather" item: the
// current METAR and TAF for the selected city's airport, from GET /aviation
// (aviation_client.dart; web/src/pages/AviationPage.tsx). Each report shows
// its plain-language briefing (English only — the decoders' fixed templates),
// the code exactly as issued, and whether it is live or an offline snapshot,
// dated. A missing report is "not available", never fair weather (plan.md §2
// principle 3), and the page always carries the not-for-flight-planning
// disclaimer.
import 'package:flutter/material.dart';

import '../aviation_client.dart';
import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../format.dart';
import '../persona_theme.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';

Future<void> openAviation(BuildContext context) {
  return Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const AviationPage()));
}

class AviationPage extends StatefulWidget {
  /// Where reports come from; tests pass a stub.
  final AviationFetcher fetcher;
  const AviationPage({super.key, this.fetcher = fetchAviation});

  @override
  State<AviationPage> createState() => _AviationPageState();
}

class _AviationPageState extends State<AviationPage> {
  String? _city;
  bool _loading = false;
  AviationData? _data;
  AviationError? _error;
  int _requestId = 0;

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
        _error = e is AviationError
            ? e
            : AviationError(AviationErrorKind.network, 'Something went wrong talking to the airport weather service.');
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
    final t = PersonaTheme.of(context);
    final city = UiPrefs.of(context).cityInfo.name;
    final data = _data;

    return SubPageScaffold(
      body: PageFrame(
        onRefresh: _reload,
        children: [
          PageHeader(
            title: 'Airport weather',
            subtitle: 'The latest METAR and TAF for $city airport, decoded into plain language.',
          ),
          const SizedBox(height: AppSpace.lg),
          if (_loading)
            const LoadingPanel('Fetching the airport reports…')
          else if (_error != null)
            ErrorPanel(
              icon: Icons.wifi_off,
              title: 'Airport weather unavailable',
              message: _error!.message,
              onRetry: _reload,
            )
          else if (data != null && data.unavailable)
            _Unavailable(data, city)
          else if (data != null) ...[
            Wrap(spacing: 6, runSpacing: 6, children: [TagChip(data.where, icon: Icons.flight)]),
            const SizedBox(height: AppSpace.md),
            const SectionTitle('Current observation'),
            const SizedBox(height: AppSpace.sm),
            _ReportCard(
              icon: Icons.visibility_outlined,
              title: 'METAR',
              subtitle: 'What the airport is reporting now',
              report: data.metar,
              missing: 'No METAR is available for this airport right now.',
            ),
            const SizedBox(height: AppSpace.lg),
            const SectionTitle('Airport forecast'),
            const SizedBox(height: AppSpace.sm),
            _ReportCard(
              icon: Icons.schedule,
              title: 'TAF',
              subtitle: "Forecast for the airport's next 24–30 hours",
              report: data.taf,
              missing: 'No TAF is available for this airport right now.',
            ),
            const SizedBox(height: AppSpace.lg),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(color: t.tint, borderRadius: BorderRadius.circular(AppRadius.xl)),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_outline, size: 16, color: t.primary),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(data.disclaimer, style: AppText.bodySm.copyWith(color: t.inkMuted)),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Neither report could be had: no verdict, and explicitly not fair weather.
class _Unavailable extends StatelessWidget {
  final AviationData data;
  final String city;
  const _Unavailable(this.data, this.city);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return AppCard(
      color: t.surfaceContainerLow,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const IconDisc(Icons.help_outline),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'No airport reports',
                      style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                    ),
                    Text(data.where, style: AppText.bodySm.copyWith(color: t.inkMuted)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            "The airport reports for $city aren't available right now — this can't be read as fair weather.",
            style: AppText.bodyMd.copyWith(color: t.ink),
          ),
        ],
      ),
    );
  }
}

class _ReportCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final AviationReport? report;
  final String missing;
  const _ReportCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.report,
    required this.missing,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final r = report;
    return AppCard(
      padding: const EdgeInsets.all(AppSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconDisc(icon, solid: true),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                          title,
                          style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                        ),
                        if (r != null) LiveBadge(live: r.isLive),
                      ],
                    ),
                    Text(subtitle, style: AppText.bodySm.copyWith(color: t.inkMuted)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.md),
          if (r == null)
            Text(missing, style: AppText.bodyMd.copyWith(color: t.inkMuted))
          else ...[
            if (!r.isLive) ...[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.tertiaryFixed,
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.history, size: 14, color: AppColors.onTertiaryFixed),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        'Snapshot taken ${istTimestamp(r.retrievedAt)} — not a live report.',
                        style: AppText.bodySm.copyWith(color: AppColors.onTertiaryFixed),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpace.sm),
            ],
            for (final line in r.lines)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpace.sm),
                child: Text(line, style: AppText.bodyMd.copyWith(color: t.ink)),
              ),
            Divider(height: AppSpace.md, color: t.outlineVariant.withValues(alpha: 0.5)),
            Text(
              [if (r.stamp != null) r.stamp!, 'source: ${r.source}'].join('   '),
              style: AppText.citationMono.copyWith(color: t.onSurfaceVariant),
            ),
            Theme(
              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                tilePadding: EdgeInsets.zero,
                childrenPadding: EdgeInsets.zero,
                title: Text(
                  'Show the code as issued',
                  style: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w600),
                ),
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(AppSpace.sm),
                    decoration: BoxDecoration(
                      color: t.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(AppRadius.lg),
                    ),
                    child: SelectableText(r.raw, style: AppText.citationMono.copyWith(color: t.onSurface)),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
