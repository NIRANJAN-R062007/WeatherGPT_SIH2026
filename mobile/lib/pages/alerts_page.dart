// Alerts & Warnings — the pics/ mockup: a featured alert card, an Active
// Alerts list and a "stay prepared" banner, fed by GET /warnings for the
// selected city (web/src/pages/AlertsPage.tsx's live card). The featured
// card is loading / error / "no verdict" (neutral, never green — no verdict
// is not an all-clear) / the IMD colour verdict, tinted by the feed's own
// colour, with its legend and provenance under "View details". The feed
// carries one warning per city, so the list holds at most that one; the
// mockup's humidity / air-quality rows have no endpoint behind them.
// Emergency numbers (GET /hotlines) follow, tap to dial; 112 shows even
// when the list can't be fetched.
//
// When the backend can't be reached, the saved warnings reply shows under a
// banner saying when it was saved; a saved "nothing in force" is shown as
// no verdict, never as an all-clear, since warnings may have been issued
// since. The saved emergency numbers show as usual.
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../components/ask_answer.dart';
import '../components/common.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../format.dart';
import '../glossary_client.dart';
import '../hotlines_client.dart';
import '../state/ui_prefs.dart';
import '../persona_theme.dart';
import '../response_cache.dart';
import '../theme.dart';
import '../warning_colors.dart';
import '../warnings_client.dart';
import '../i18n.dart';

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

  /// When the warnings reply on show was saved, if it's a saved copy.
  DateTime? _savedAt;

  /// GET /hotlines: null while loading; [_hotlinesFailed] when it couldn't
  /// be had, and only 112 is shown.
  HotlineList? _hotlines;
  bool _hotlinesFailed = false;

  /// GET /glossary in the app language: the colour legend's words; null
  /// until (or unless) it answers, and /warnings' own legend stands in.
  Glossary? _glossary;

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
      _hotlines = null;
    }
    _city = city;
    _lang = lang;
    _loading = true;
    _error = null;
    _savedAt = null;
    _hotlinesFailed = false;
    final id = ++_requestId;
    return Future.wait([_fetch(id, city, lang), _fetchHotlines(id, city, lang), _fetchGlossary(id, lang)]);
  }

  Future<void> _fetchGlossary(int id, String lang) async {
    try {
      final glossary = await fetchGlossary(lang: lang, cache: ResponseCacheScope.of(context));
      if (!mounted || id != _requestId) return;
      setState(() => _glossary = glossary);
    } catch (_) {
      // /warnings' own legend stands in.
    }
  }

  Future<void> _fetchHotlines(int id, String city, String lang) async {
    try {
      final list = await fetchHotlines(city: city, lang: lang, cache: ResponseCacheScope.of(context));
      if (!mounted || id != _requestId) return;
      setState(() => _hotlines = list);
    } catch (_) {
      if (!mounted || id != _requestId) return;
      setState(() {
        _hotlines = null;
        _hotlinesFailed = true;
      });
    }
  }

  Future<void> _fetch(int id, String city, String lang) async {
    try {
      final (data, savedAt) = await fetchWarningsOrSaved(
        city: city,
        lang: lang,
        cache: ResponseCacheScope.of(context),
      );
      if (!mounted || id != _requestId) return;
      setState(() {
        _data = data;
        _savedAt = savedAt;
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
    final city = tr(context, prefs.cityInfo.name);
    final active =
        warning != null && (data!['status'] ?? (warning['colour'] == 'green' ? 'clear' : 'active')) == 'active';
    // A saved "nothing in force" says nothing about now.
    final savedAt = _savedAt;
    final verdictNow = warning != null && (savedAt == null || active);

    return PageFrame(
      onRefresh: _reload,
      children: [
        PageHeader(title: 'Alerts & Warnings', subtitle: prefs.personaInfo.alertsLead),
        const SizedBox(height: AppSpace.lg),
        if (!_loading && savedAt != null) ...[
          SavedDataBanner(
            message: "Couldn't reach the warnings service. This was saved at {time}; newer warnings can't be checked now.",
            messageArgs: {'time': savedTimeLabel(savedAt, langOf(context))},
            onRetry: _reload,
          ),
          const SizedBox(height: AppSpace.md),
        ],
        if (_loading)
          const LoadingPanel('Checking current warnings…')
        else if (_error != null)
          ErrorPanel(
            icon: Icons.wifi_off,
            title: 'Warnings service unreachable',
            message: _error!.message,
            messageArgs: _error!.args,
            onRetry: _reload,
          )
        else if (verdictNow)
          _Verdict(
            data!,
            glossary: _glossary,
            active: active,
            expanded: _showDetails,
            onToggle: () => setState(() => _showDetails = !_showDetails),
          )
        else if (data != null)
          _NoVerdict(data, glossary: _glossary),
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
                    verdictNow
                        ? tr(context, 'No active alerts for {city}.', {'city': city})
                        : tr(context, 'Alerts for {city} will be listed here when the warnings feed has a verdict.', {
                            'city': city,
                          }),
                    style: AppText.bodyMd.copyWith(color: t.inkMuted),
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: AppSpace.lg),
        const SectionTitle('Emergency numbers'),
        const SizedBox(height: AppSpace.sm),
        _Hotlines(list: _hotlines, failed: _hotlinesFailed),
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
  final Glossary? glossary;
  const _NoVerdict(this.data, {this.glossary});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final cityName = tr(context, data['city_name'] as String? ?? cityLabel(data['city'] as String?));
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
                      tr(context, 'No warning verdict'),
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
            tr(
              context,
              "Weather warnings aren't available right now for {city} — this can't be read as an all-clear.",
              {'city': cityName},
            ),
            style: AppText.bodyMd.copyWith(color: t.onSurface),
          ),
          const SizedBox(height: AppSpace.sm),
          _Legend(data, glossary: glossary),
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
  final Glossary? glossary;
  const _Verdict(
    this.data, {
    required this.active,
    required this.expanded,
    required this.onToggle,
    this.glossary,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final w = data['warning'] as Map<String, dynamic>;
    final colour = w['colour'] as String?;
    final tone = warningColor(colour);
    String s(String k) => w[k] is String ? w[k] as String : '';
    final category = s('category_label');
    final title = active
        ? (category.isNotEmpty
              ? tr(context, '{category} Alert', {'category': category})
              : tr(context, '{colour} warning', {'colour': s('colour_label')}))
        : tr(context, 'No warnings in force');
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
                          TagChip('${s('colour_label')} — ${tr(context, active ? 'in force' : 'nothing in force')}'),
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
                  child: Container(
                    constraints: const BoxConstraints(minHeight: kMinInteractiveDimension),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Flexible(
                          child: Text(
                            tr(context, expanded ? 'Hide details' : 'View details'),
                            style: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w600),
                          ),
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
            _Legend(data, glossary: glossary, highlight: colour),
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
                    Text(
                      tr(context, 'Valid {from} → {to}', {
                        'from': istTimestamp(s('valid_from')),
                        'to': istTimestamp(s('valid_to')),
                      }),
                    ),
                    Text('${tr(context, 'source')}: ${s('source')}', style: TextStyle(color: t.outline)),
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

/// The IMD colour legend from GET /glossary (the shared, reviewed-or-not
/// wording) when it answered, else /warnings' own; a translation no native
/// speaker has checked yet is marked as such.
class _Legend extends StatelessWidget {
  final Map<String, dynamic> data;
  final Glossary? glossary;
  final String? highlight;
  const _Legend(this.data, {this.glossary, this.highlight});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final fromGlossary = glossary?.legend;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        WarningLegend(rows: fromGlossary ?? data['legend'], highlight: highlight),
        if (fromGlossary != null && !glossary!.legendReviewed)
          Text(
            tr(context, 'These translations have not been reviewed by a native speaker yet.'),
            style: AppText.bodySm.copyWith(color: t.inkMuted),
          ),
      ],
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
      detail: s('valid_to').isEmpty ? null : tr(context, 'Until {time}', {'time': istTimestamp(s('valid_to'))}),
      onTap: onTap,
    );
  }
}

/// The city's emergency numbers, each a row that opens the dialer; 112
/// alone (with a note saying why) until or unless the list arrives.
class _Hotlines extends StatelessWidget {
  final HotlineList? list;
  final bool failed;
  const _Hotlines({required this.list, required this.failed});

  Future<void> _dial(BuildContext context, Hotline line) async {
    final messenger = ScaffoldMessenger.maybeOf(context);
    final lang = langOf(context);
    var opened = false;
    try {
      opened = await launchUrl(Uri(scheme: 'tel', path: line.dial));
    } catch (_) {}
    if (!opened) {
      messenger?.showSnackBar(
        SnackBar(
          content: Text(trIn(lang, "Couldn't open the phone app. Dial {number} yourself.", {'number': line.number})),
        ),
      );
    }
  }

  /// One number: a row that opens the dialer, read out as "Call …, …".
  Widget _line(BuildContext context, Hotline line) {
    final t = PersonaTheme.of(context);
    final number = Text(
      line.number,
      style: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w700, fontSize: 15),
    );
    final call = Icon(Icons.call, size: 18, color: t.primary);
    // At large text sizes the number goes under the name, so a long one
    // (040 2111 1111) doesn't squeeze the name into a sliver.
    final large = isLargeText(context);
    return Semantics(
      button: true,
      label: tr(context, 'Call {name}, {number}', {'name': tr(context, line.name), 'number': line.number}),
      excludeSemantics: true,
      child: ActionRow(
        icon: line.dial == '112' ? Icons.emergency_outlined : Icons.support_agent,
        iconColor: line.dial == '112' ? Theme.of(context).colorScheme.error : null,
        title: line.name,
        subtitle: line.note.isEmpty ? null : line.note,
        onTap: () => _dial(context, line),
        below: large ? number : null,
        trailing: large
            ? call
            : Row(mainAxisSize: MainAxisSize.min, children: [number, const SizedBox(width: 6), call]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final lang = langOf(context);
    final lines = list?.lines ?? const [kEmergencyHotline];
    final checked = DateTime.tryParse(list?.checked ?? '');
    final String? footnote = failed
        ? tr(context, "Couldn't load the local numbers. 112 works anywhere in India.")
        : checked == null
        ? null
        : tr(context, 'Checked against official government pages on {date}.', {
            'date': '${dayMonth(checked, lang)} ${checked.year}',
          });

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final line in lines) ...[_line(context, line), const SizedBox(height: AppSpace.sm)],
        if (footnote != null) Text(footnote, style: AppText.bodySm.copyWith(color: t.inkMuted)),
      ],
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
              Text(tr(context, 'Source'), style: AppText.labelMd.copyWith(fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            tr(
              context,
              "The colour code and headline are the warning feed's own, shown verbatim — WeatherGPT explains a colour, it never re-grades one. The source line on each verdict names the feed that answered.",
            ),
            style: AppText.bodySm.copyWith(color: t.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}
