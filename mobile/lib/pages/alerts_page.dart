// Alerts & Warnings — the pics/ mockup: a featured alert card, an Active
// Alerts list and a "stay prepared" banner, fed by GET /warnings for the
// selected city (web/src/pages/AlertsPage.tsx's live card). The featured
// card is loading / error / "no verdict" (neutral, never green — no verdict
// is not an all-clear) / the IMD colour verdict, tinted by the feed's own
// colour, with its legend and provenance under "View details". The feed
// carries one warning per city, so the list holds at most that one; the
// mockup's humidity / air-quality rows have no endpoint behind them.
import 'package:flutter/material.dart';

import '../components/ask_answer.dart';
import '../components/common.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../format.dart';
import '../state/ui_prefs.dart';
import '../persona_theme.dart';
import '../theme.dart';
import '../warning_colors.dart';
import '../warnings_client.dart';

class AlertsPage extends StatefulWidget {
  const AlertsPage({super.key});

  @override
  State<AlertsPage> createState() => _AlertsPageState();
}

class _AlertsPageState extends State<AlertsPage> {
  String? _city;
  String? _lang;
  bool _loading = false;
  Map<String, dynamic>? _data;
  WarningsError? _error;
  int _requestId = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Fetch on first build and whenever the shared city or language changes.
    // A build always follows, so no setState here.
    final prefs = UiPrefs.of(context);
    if (prefs.city != _city || prefs.lang != _lang) _load(prefs.city, prefs.lang);
  }

  /// Synchronous part is plain assignment — callers outside a build wrap
  /// the call in setState.
  Future<void> _load(String city, String lang) {
    if (city != _city) {
      _data = null;
      _showDetails = false;
    }
    _city = city;
    _lang = lang;
    _loading = true;
    _error = null;
    return _fetch(++_requestId, city, lang);
  }

  Future<void> _fetch(int id, String city, String lang) async {
    try {
      final data = await fetchWarnings(city: city, lang: lang);
      if (!mounted || id != _requestId) return;
      setState(() {
        _data = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || id != _requestId) return;
      setState(() {
        _error = e is WarningsError
            ? e
            : WarningsError(WarningsErrorKind.network, 'Something went wrong talking to the warnings service.');
        _data = null;
        _loading = false;
      });
    }
  }

  Future<void> _reload() {
    final prefs = UiPrefs.read(context);
    late Future<void> done;
    setState(() => done = _load(prefs.city, prefs.lang));
    return done;
  }

  bool _showDetails = false;

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final data = _data;
    final warning = data?['warning'] is Map<String, dynamic> ? data!['warning'] as Map<String, dynamic> : null;
    final prefs = UiPrefs.of(context);
    final city = prefs.cityInfo.name;
    final active =
        warning != null && (data!['status'] ?? (warning['colour'] == 'green' ? 'clear' : 'active')) == 'active';

    return PageFrame(
      onRefresh: _reload,
      children: [
        PageHeader(title: 'Alerts & Warnings', subtitle: prefs.personaInfo.alertsLead),
        const SizedBox(height: AppSpace.lg),
        if (_loading)
          const LoadingPanel('Checking current warnings…')
        else if (_error != null)
          ErrorPanel(
            icon: Icons.wifi_off,
            title: 'Warnings service unreachable',
            message: _error!.message,
            onRetry: _reload,
          )
        else if (warning != null)
          _Verdict(
            data!,
            active: active,
            expanded: _showDetails,
            onToggle: () => setState(() => _showDetails = !_showDetails),
          )
        else if (data != null)
          _NoVerdict(data),
        const SizedBox(height: AppSpace.lg),
        const SectionTitle('Active Alerts'),
        const SizedBox(height: AppSpace.sm),
        if (active)
          _AlertRow(data, onTap: () => setState(() => _showDetails = true))
        else
          AppCard(
            child: Row(
              children: [
                const IconDisc(Icons.notifications_none_rounded, size: 36),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    warning != null
                        ? 'No active alerts for $city.'
                        : 'Alerts for $city will be listed here when the warnings feed has a verdict.',
                    style: AppText.bodyMd.copyWith(color: t.inkMuted),
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: AppSpace.lg),
        InfoBanner(
          icon: prefs.personaInfo.icon,
          title: 'Stay prepared.',
          body: 'Check for updates regularly — pull down to refresh.',
        ),
        const SizedBox(height: AppSpace.md),
        const _SourceNote(),
      ],
    );
  }
}

/// `status` "unavailable" (or an older backend's bare `warning: null`):
/// deliberately neutral, never green — no verdict is not an all-clear.
class _NoVerdict extends StatelessWidget {
  final Map<String, dynamic> data;
  const _NoVerdict(this.data);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final cityName = data['city_name'] as String? ?? cityLabel(data['city'] as String?);
    return AppCard(
      color: t.surfaceContainerLow,
      borderColor: t.outlineVariant,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              IconDisc(Icons.help_outline, color: t.onSurfaceVariant, background: t.surfaceContainerHigh),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'No warning verdict',
                      style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                    ),
                    Text(cityName, style: AppText.bodySm.copyWith(color: t.inkMuted)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            "Weather warnings aren't available right now for $cityName — this can't be read as an all-clear.",
            style: AppText.bodyMd.copyWith(color: t.onSurface),
          ),
          const SizedBox(height: AppSpace.sm),
          WarningLegend(rows: data['legend']),
        ],
      ),
    );
  }
}

/// The featured card: tinted by the feed's own colour, headline up front,
/// the legend and provenance behind "View details".
class _Verdict extends StatelessWidget {
  final Map<String, dynamic> data;
  final bool active;
  final bool expanded;
  final VoidCallback onToggle;
  const _Verdict(this.data, {required this.active, required this.expanded, required this.onToggle});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final w = data['warning'] as Map<String, dynamic>;
    final colour = w['colour'] as String?;
    final tone = warningColor(colour);
    String s(String k) => w[k] is String ? w[k] as String : '';
    final category = s('category_label');
    final title = active
        ? (category.isNotEmpty ? '$category Alert' : '${s('colour_label')} warning')
        : 'No warnings in force';
    final disclaimer = disclaimerBanner(w);

    return AppCard(
      color: Color.alphaBlend(tone.withValues(alpha: 0.08), t.card),
      borderColor: tone.withValues(alpha: 0.35),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              IconDisc(active ? Icons.priority_high_rounded : Icons.check_rounded, color: tone, solid: true, size: 36),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: AppText.labelMd.copyWith(color: tone, fontWeight: FontWeight.w700, fontSize: 15),
                    ),
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: [
                        TagChip(
                          data['city_name'] as String? ?? cityLabel(data['city'] as String?),
                          icon: Icons.location_on_outlined,
                        ),
                        if (s('colour_label').isNotEmpty)
                          TagChip('${s('colour_label')}${active ? ' — in force' : ' — nothing in force'}'),
                      ],
                    ),
                    const SizedBox(height: AppSpace.sm),
                    Text(s('headline'), style: AppText.bodyMd.copyWith(color: t.ink)),
                    if (disclaimer != null) ...[
                      const SizedBox(height: AppSpace.sm),
                      disclaimer,
                    ],
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Align(
            alignment: Alignment.centerLeft,
            child: Padding(
              padding: const EdgeInsets.only(left: 48),
              child: Material(
                color: t.card,
                borderRadius: BorderRadius.circular(999),
                child: InkWell(
                  borderRadius: BorderRadius.circular(999),
                  onTap: onToggle,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          expanded ? 'Hide details' : 'View details',
                          style: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(width: 4),
                        Icon(expanded ? Icons.expand_less : Icons.arrow_forward, size: 16, color: t.primary),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          if (expanded) ...[
            if (s('advice').isNotEmpty) ...[
              const SizedBox(height: AppSpace.md),
              Text(s('advice'), style: AppText.bodyMd.copyWith(color: t.inkMuted)),
            ],
            const SizedBox(height: AppSpace.md),
            WarningLegend(rows: data['legend'], highlight: colour),
            const SizedBox(height: AppSpace.sm),
            Container(
              padding: const EdgeInsets.only(top: AppSpace.xs),
              decoration: BoxDecoration(
                border: Border(top: BorderSide(color: t.outlineVariant.withValues(alpha: 0.4))),
              ),
              child: DefaultTextStyle.merge(
                style: AppText.citationMono.copyWith(color: t.onSurfaceVariant),
                child: Wrap(
                  spacing: 12,
                  runSpacing: 4,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.campaign_outlined, size: 12, color: t.onSurfaceVariant),
                        const SizedBox(width: 4),
                        Flexible(child: Text(s('issued_by'))),
                      ],
                    ),
                    Text('Valid ${istTimestamp(s('valid_from'))} → ${istTimestamp(s('valid_to'))}'),
                    Text('source: ${s('source')}', style: TextStyle(color: t.outline)),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// The one active warning as an Active Alerts row.
class _AlertRow extends StatelessWidget {
  final Map<String, dynamic> data;
  final VoidCallback onTap;
  const _AlertRow(this.data, {required this.onTap});

  @override
  Widget build(BuildContext context) {
    final w = data['warning'] as Map<String, dynamic>;
    final tone = warningColor(w['colour'] as String?);
    String s(String k) => w[k] is String ? w[k] as String : '';
    final category = s('category_label');
    return ActionRow(
      icon: Icons.warning_amber_rounded,
      iconColor: tone,
      title: category.isNotEmpty ? category : s('colour_label'),
      subtitle: data['city_name'] as String? ?? cityLabel(data['city'] as String?),
      detail: s('valid_to').isEmpty ? null : 'Until ${istTimestamp(s('valid_to'))}',
      onTap: onTap,
    );
  }
}

/// AlertsPage.tsx's source note, reworded to what the backend actually does.
class _SourceNote extends StatelessWidget {
  const _SourceNote();

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.verified_outlined, size: 18, color: t.primary),
              const SizedBox(width: AppSpace.sm),
              Text('Source', style: AppText.labelMd.copyWith(fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            'The colour code and headline are the warning feed\'s own, shown verbatim — WeatherGPT '
            'explains a colour, it never re-grades one. The source line on each verdict names the feed '
            'that answered.',
            style: AppText.bodySm.copyWith(color: t.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}
