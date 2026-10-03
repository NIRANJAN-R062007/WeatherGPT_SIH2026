// Renders one /ask result — a branch-for-branch port of
// web/src/components/AskAnswer.tsx, so both clients show the same thing for
// the same backend response. In particular a refusal carries `message`, not
// `response`, and an unavailable warning is never shown as an all-clear.
// Every field read is null-tolerant: the deployed orchestrator can lag main
// (e.g. no `status`/`legend` on the warnings branch).
import 'package:flutter/material.dart';

import '../api_client.dart';
import '../format.dart';
import '../play_button.dart';
import '../persona_theme.dart';
import '../theme.dart';
import '../warning_colors.dart';
import 'common.dart';
import '../i18n.dart';

class AskAnswer extends StatelessWidget {
  final String? asked;
  final bool loading;
  final AskOutcome? outcome;
  final AskError? error;

  /// Legend + per-figure evidence are hidden by default on compact panels.
  final bool detail;

  /// When set, grounded and warnings answers get a Listen (POST /tts)
  /// button that speaks in this language.
  final String? playbackLang;

  const AskAnswer({
    super.key,
    this.asked,
    this.loading = false,
    this.outcome,
    this.error,
    this.detail = false,
    this.playbackLang,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    if (!loading && outcome == null && error == null) return const SizedBox.shrink();
    final o = outcome;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: _gap([
        if (asked != null)
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Padding(
              padding: EdgeInsets.only(top: 2),
              child: Icon(Icons.chat_outlined, size: 14, color: t.outline),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                '“$asked”',
                style: AppText.bodySm.copyWith(color: t.onSurfaceVariant, fontStyle: FontStyle.italic),
              ),
            ),
          ]),
        if (loading) const LoadingPanel('Grounding an answer against live weather data…'),
        if (error != null) _errorPanel(context, error!),
        if (o != null)
          switch (o.kind) {
            AskKind.success => _Success(o.data, detail: detail, playbackLang: playbackLang),
            AskKind.warnings => _Warnings(o.data, detail: detail, playbackLang: playbackLang),
            AskKind.warningsUnavailable => _WarningsUnavailable(o.data, detail: detail),
            AskKind.ungrounded => _Ungrounded(o.data),
            AskKind.fallback => _Fallback(o.data),
          },
      ]),
    );
  }

  static Widget _errorPanel(BuildContext context, AskError e) {
    final (icon, title) = switch (e.kind) {
      AskErrorKind.http => (
          Icons.error_outline,
          '${tr(context, 'Weather service error')}${e.status != null ? ' (HTTP ${e.status})' : ''}',
        ),
      AskErrorKind.timeout => (Icons.timer_off_outlined, 'Request timed out'),
      AskErrorKind.malformed => (Icons.report_outlined, 'Unreadable reply'),
      AskErrorKind.network => (Icons.wifi_off, 'Weather service unreachable'),
    };
    return ErrorPanel(icon: icon, title: title, message: e.message, messageArgs: e.args);
  }
}

List<Widget> _gap(List<Widget> children, [double gap = AppSpace.sm]) => [
      for (var i = 0; i < children.length; i++) ...[
        if (i > 0) SizedBox(height: gap),
        children[i],
      ],
    ];

Map<String, dynamic> _map(Object? v) => v is Map<String, dynamic> ? v : const {};
String _str(Object? v) => v is String ? v : '';
int _int(Object? v) => v is num ? v.toInt() : 0;

String _intentLabel(Object? intent) => _str(intent).replaceAll('_', ' ').toUpperCase();

class _Panel extends StatelessWidget {
  final Color color;
  final List<Widget> children;
  const _Panel({required this.color, required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(AppRadius.xl)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: _gap(children)),
    );
  }
}

/// Chip row with an optional Listen button pinned to the right.
class _Header extends StatelessWidget {
  final List<Widget> chips;
  final String? speak;
  final String? lang;
  const _Header({required this.chips, this.speak, this.lang});

  @override
  Widget build(BuildContext context) {
    final wrap = Wrap(
      spacing: 6,
      runSpacing: 6,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: chips,
    );
    final text = speak;
    final l = lang;
    if (text == null || text.isEmpty || l == null) return wrap;
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Expanded(child: Padding(padding: const EdgeInsets.only(top: 12), child: wrap)),
      PlayButton(text: text, lang: l),
    ]);
  }
}

class _StatusTitle extends StatelessWidget {
  final IconData icon;
  final String text;
  final Color color;
  const _StatusTitle(this.icon, this.text, this.color);

  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 18, color: color),
      const SizedBox(width: 4),
      Flexible(
        child: Text(tr(context, text), style: AppText.labelMd.copyWith(color: color, fontWeight: FontWeight.w700)),
      ),
    ]);
  }
}

/// The `notice` line (e.g. "language not supported, answering in English").
class _Notice extends StatelessWidget {
  final String text;
  const _Notice(this.text);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.tertiaryFixed,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Padding(
          padding: EdgeInsets.only(top: 2),
          child: Icon(Icons.translate, size: 14, color: AppColors.onTertiaryFixed),
        ),
        const SizedBox(width: 6),
        Expanded(child: Text(text, style: AppText.bodySm.copyWith(color: AppColors.onTertiaryFixed))),
      ]),
    );
  }
}

Widget? _notice(Map<String, dynamic> data) {
  final n = data['notice'];
  return n is String && n.isNotEmpty ? _Notice(n) : null;
}

class _GroundedBadge extends StatelessWidget {
  final int matched;
  final int total;
  const _GroundedBadge(this.matched, this.total);

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tr(context, '{matched} of {total} figures matched the source data', {'matched': matched, 'total': total}),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: AppColors.secondaryContainer,
          borderRadius: BorderRadius.circular(AppRadius.sm),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.verified_user_outlined, size: 12, color: AppColors.onSecondaryContainer),
          const SizedBox(width: 4),
          // Wraps rather than overflow: the Tamil label is long at large text sizes.
          Flexible(
            child: Text(
              tr(context, 'GROUNDED {matched}/{total}', {'matched': matched, 'total': total}),
              style: AppText.chipMono.copyWith(color: AppColors.onSecondaryContainer, fontWeight: FontWeight.w700),
            ),
          ),
        ]),
      ),
    );
  }
}

/// `border-t border-outline-variant/40 font-citation-mono` provenance line.
class _Footer extends StatelessWidget {
  final List<Widget> children;
  const _Footer(this.children);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Container(
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
          children: children,
        ),
      ),
    );
  }
}

class _IconText extends StatelessWidget {
  final IconData icon;
  final String text;
  const _IconText(this.icon, this.text);

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 12, color: PersonaTheme.of(context).onSurfaceVariant),
        const SizedBox(width: 4),
        Flexible(child: Text(text)),
      ]);
}

class _WeatherProvenance extends StatelessWidget {
  final Map<String, dynamic> p;
  final Map<String, dynamic> g;
  const _WeatherProvenance(this.p, this.g);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final attempts = _int(g['attempts']);
    final issued = p['issued'];
    return _Footer([
      _IconText(Icons.storage, _str(p['source'])),
      LiveBadge(live: p['is_live'] == true),
      if (issued is String && issued.isNotEmpty) Text(tr(context, 'Issued {time}', {'time': istTimestamp(issued)})),
      if (p['retrieved_at'] is String) Text(tr(context, 'Retrieved {time}', {'time': istTimestamp(p['retrieved_at'] as String)})),
      Text(
        '${_str(g['narration'])} · ${_str(g['provider'])}'
        '${attempts > 1 ? ' · ${tr(context, '{n} attempts', {'n': attempts})}' : ''}'
        '${g['fallback_used'] == true ? ' · ${tr(context, 'fell back to template')}' : ''}',
        style: TextStyle(color: t.outline),
      ),
    ]);
  }
}

/// Per-figure guardrail evidence: every number in the narration, and
/// whether it matched a value in the source data.
class _FigureList extends StatelessWidget {
  final Object? figures;
  const _FigureList(this.figures);

  @override
  Widget build(BuildContext context) {
    final list = figures is List ? (figures as List).whereType<Map<String, dynamic>>().toList() : const [];
    if (list.isEmpty) return const SizedBox.shrink();
    return Wrap(spacing: 6, runSpacing: 6, children: [
      for (final f in list)
        Tooltip(
          message: f['matched'] == true
              ? tr(context, 'matched {path}', {'path': _str(f['path'])})
              : tr(context, 'no matching value in the source data'),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: f['matched'] == true ? AppColors.secondaryContainer : AppColors.errorContainer,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(
                f['matched'] == true ? Icons.check_circle_outline : Icons.cancel_outlined,
                size: 12,
                color: f['matched'] == true ? AppColors.onSecondaryContainer : AppColors.onErrorContainer,
              ),
              const SizedBox(width: 4),
              Text(
                _str(f['reading']),
                style: AppText.citationMono.copyWith(
                  color: f['matched'] == true ? AppColors.onSecondaryContainer : AppColors.onErrorContainer,
                ),
              ),
            ]),
          ),
        ),
    ]);
  }
}

/// glossary.legend(lang): the four IMD colour rows. Shared with the Alerts
/// page, like web/'s exported Legend.
class WarningLegend extends StatelessWidget {
  final Object? rows;
  final String? highlight;
  const WarningLegend({super.key, required this.rows, this.highlight});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final list = rows is List ? (rows as List).whereType<Map<String, dynamic>>().toList() : const [];
    if (list.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final row in list)
          Container(
            margin: const EdgeInsets.only(bottom: 4),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: row['colour'] == highlight ? t.surfaceContainer : null,
              borderRadius: BorderRadius.circular(AppRadius.lg),
            ),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                margin: const EdgeInsets.only(top: 4),
                width: 10,
                height: 10,
                decoration: BoxDecoration(color: warningColor(row['colour'] as String?), shape: BoxShape.circle),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Text.rich(
                  TextSpan(children: [
                    TextSpan(text: _str(row['label']), style: const TextStyle(fontWeight: FontWeight.w600)),
                    TextSpan(text: ' — ${_str(row['meaning'])}'),
                  ]),
                  style: AppText.bodySm.copyWith(
                    color: row['colour'] == highlight ? t.onSurface : t.onSurfaceVariant,
                  ),
                ),
              ),
            ]),
          ),
      ],
    );
  }
}

/// The 6px IMD colour band across the top of a verdict.
class WarningBand extends StatelessWidget {
  final String? colour;
  const WarningBand(this.colour, {super.key});

  @override
  Widget build(BuildContext context) => Container(
        height: 6,
        decoration: BoxDecoration(color: warningColor(colour), borderRadius: BorderRadius.circular(999)),
      );
}

class _Success extends StatelessWidget {
  final Map<String, dynamic> data;
  final bool detail;
  final String? playbackLang;
  const _Success(this.data, {required this.detail, this.playbackLang});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final g = _map(data['grounding']);
    final response = _str(data['response']);
    return _Panel(color: t.surfaceContainerLow, children: [
      _Header(
        speak: response,
        lang: playbackLang,
        chips: [
          _GroundedBadge(_int(g['matched']), _int(g['total'])),
          TagChip(_intentLabel(data['intent']), tone: ChipTone.primary),
          TagChip(cityLabel(data['city'] as String?), icon: Icons.location_on_outlined),
          TagChip(dayLabel(data['day'])),
        ],
      ),
      ?_notice(data),
      Text(response, style: AppText.bodyLg.copyWith(color: t.onSurface)),
      if (detail) _FigureList(g['figures']),
      _WeatherProvenance(_map(data['provenance']), g),
    ]);
  }
}

class _Warnings extends StatelessWidget {
  final Map<String, dynamic> data;
  final bool detail;
  final String? playbackLang;
  const _Warnings(this.data, {required this.detail, this.playbackLang});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final w = _map(data['warning']);
    final p = _map(data['provenance']);
    final g = _map(data['grounding']);
    final colour = w['colour'] as String?;
    final active = (data['status'] ?? (colour == 'green' ? 'clear' : 'active')) == 'active';
    final response = _str(data['response']);
    final advice = _str(w['advice']);
    return _Panel(color: t.surfaceContainerLow, children: [
      WarningBand(colour),
      _Header(
        speak: response,
        lang: playbackLang,
        chips: [
          _StatusTitle(
            active ? Icons.warning_amber : Icons.check_circle_outline,
            '${_str(w['colour_label'])} — ${tr(context, active ? 'in force' : 'nothing in force')}',
            warningColor(colour),
          ),
          TagChip(_str(w['district']), icon: Icons.location_on_outlined),
          if (_str(w['category_label']).isNotEmpty) TagChip(_str(w['category_label']), tone: ChipTone.primary),
        ],
      ),
      ?_notice(data),
      // The feed's own headline, verbatim — not narrated, not translated.
      Text(response, style: AppText.bodyLg.copyWith(color: t.onSurface)),
      if (advice.isNotEmpty) Text(advice, style: AppText.bodyMd.copyWith(color: t.onSurfaceVariant)),
      ?disclaimerBanner(w),
      if (detail) WarningLegend(rows: data['legend'], highlight: colour),
      _Footer([
        _IconText(Icons.campaign_outlined, _str(p['issued_by'] ?? w['issued_by'])),
        LiveBadge(live: p['is_live'] == true, liveText: 'LIVE FEED', notLiveText: 'FIXTURE'),
        Text(tr(context, 'Valid {from} → {to}', {
          'from': istTimestamp(_str(p['valid_from'] ?? w['valid_from'])),
          'to': istTimestamp(_str(p['valid_to'] ?? w['valid_to'])),
        })),
        Text('${tr(context, 'verbatim')} · ${_str(g['provider'])}', style: TextStyle(color: t.outline)),
      ]),
    ]);
  }
}

class _WarningsUnavailable extends StatelessWidget {
  final Map<String, dynamic> data;
  final bool detail;
  const _WarningsUnavailable(this.data, {required this.detail});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    // Deliberately neutral, never green: no verdict is not an all-clear.
    return _Panel(color: t.surfaceContainer, children: [
      Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
        _StatusTitle(Icons.help_outline, 'No warning verdict', t.onSurfaceVariant),
        TagChip(cityLabel(data['city'] as String?), icon: Icons.location_on_outlined),
        TagChip('${tr(context, 'STATUS')}: ${tr(context, _str(data['status'] ?? 'unavailable')).toUpperCase()}'),
      ]),
      ?_notice(data),
      Text(_str(data['message']), style: AppText.bodyMd.copyWith(color: t.onSurface)),
      if (detail) WarningLegend(rows: data['legend']),
    ]);
  }
}

class _Ungrounded extends StatelessWidget {
  final Map<String, dynamic> data;
  const _Ungrounded(this.data);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final g = _map(data['grounding']);
    return _Panel(color: AppColors.errorContainer, children: [
      Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
        const _StatusTitle(Icons.gpp_maybe_outlined, 'Answer withheld — not grounded', AppColors.onErrorContainer),
        TagChip(cityLabel(data['city'] as String?), icon: Icons.location_on_outlined),
        TagChip(tr(context, '{matched}/{total} figures matched', {'matched': _int(g['matched']), 'total': _int(g['total'])})),
      ]),
      ?_notice(data),
      Text(_str(data['message']), style: AppText.bodyMd.copyWith(color: AppColors.onErrorContainer)),
      Container(
        padding: const EdgeInsets.all(AppSpace.sm),
        decoration: BoxDecoration(
          color: t.surfaceContainerLowest,
          borderRadius: BorderRadius.circular(AppRadius.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: _gap([_FigureList(g['figures']), _WeatherProvenance(_map(data['provenance']), g)]),
        ),
      ),
    ]);
  }
}

class _Fallback extends StatelessWidget {
  final Map<String, dynamic> data;
  const _Fallback(this.data);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final city = data['city'] as String?;
    final nluCity = _map(data['nlu'])['city'] as String?;
    return _Panel(color: t.surfaceContainer, children: [
      Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
        _StatusTitle(Icons.info_outline, 'No answer', t.onSurfaceVariant),
        TagChip(_intentLabel(data['intent']), tone: ChipTone.primary),
        // Only the no_data branch carries a resolved city key; on
        // unsupported_city the rejected name survives only in nlu.city.
        if (city != null && city.isNotEmpty)
          TagChip(cityLabel(city), icon: Icons.location_on_outlined)
        else if (nluCity != null && nluCity.isNotEmpty)
          TagChip(tr(context, 'asked about “{city}”', {'city': nluCity})),
      ]),
      ?_notice(data),
      Text(_str(data['message']), style: AppText.bodyMd.copyWith(color: t.onSurface)),
    ]);
  }
}
