// Travel advice and Sowing advice (plan.md TFA-13), opened from the drawer:
// a short conversation with POST /advisory/travel or /advisory/sowing
// (advisory_client.dart). The backend asks for what it still needs (where
// from, where to, which day; which crop, which district), one question at a
// time, then answers with a verdict and the reasons behind it, all from
// weather data; the page shows the verdict as a coloured badge, the reasons
// for and against, any best time window, the sources, and the backend's
// disclaimer. The reasons come in English only, and the page says so.
import 'package:flutter/material.dart';

import '../advisory_client.dart';
import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../format.dart';
import '../persona_theme.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import '../warning_colors.dart';
import '../i18n.dart';

Future<void> openAdvisory(BuildContext context, AdvisoryKind kind) {
  return Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => AdvisoryPage(kind: kind)));
}

/// What each advisory says about itself, as ui_strings.json keys.
({String title, String lead, List<String> examples, IconData icon}) _about(AdvisoryKind kind) => switch (kind) {
  AdvisoryKind.travel => (
    title: 'Travel advice',
    lead: 'Ask whether the weather suits a trip: where from, where to, which day, and how you are going.',
    examples: ['Chennai to Madurai tomorrow by train', 'Can I drive from Bengaluru to Mumbai today?'],
    icon: Icons.route_outlined,
  ),
  AdvisoryKind.sowing => (
    title: 'Sowing advice',
    lead: 'Ask whether the weather suits sowing a crop in your district.',
    examples: ['When should I sow groundnut in Madurai?', 'Paddy in Coimbatore'],
    icon: Icons.agriculture_outlined,
  ),
};

/// The slots in reading order (where from, where to, when, how; crop,
/// where), each as the app shows it: a city's name, Today / Tomorrow, or the
/// value capitalised.
List<String> _slotLabels(BuildContext context, Map<String, String> slots) => [
  for (final key in const ['origin', 'destination', 'day', 'mode', 'crop', 'district'])
    if (slots[key] case final value?)
      switch (key) {
        'origin' || 'destination' || 'district' => tr(context, cityLabel(value)),
        'day' when value == 'today' || value == 'tomorrow' => tr(context, sentenceCase(value)),
        _ => sentenceCase(value),
      },
];

class _Turn {
  final String text;
  AdvisoryReply? reply;
  AdvisoryError? error;
  _Turn(this.text);
}

class AdvisoryPage extends StatefulWidget {
  final AdvisoryKind kind;

  /// Where replies come from; tests pass a stub.
  final AdvisoryFetcher fetcher;
  const AdvisoryPage({super.key, required this.kind, this.fetcher = fetchAdvisory});

  @override
  State<AdvisoryPage> createState() => _AdvisoryPageState();
}

class _AdvisoryPageState extends State<AdvisoryPage> {
  final List<_Turn> _turns = [];
  final TextEditingController _input = TextEditingController();
  bool _busy = false;

  /// Carried from the last reply into the next turn.
  Map<String, String> _slots = const {};
  String? _asking;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _send(String raw) async {
    final text = raw.trim();
    if (text.isEmpty || _busy) return;
    final lang = UiPrefs.read(context).lang;
    final turn = _Turn(text);
    setState(() {
      _turns.add(turn);
      _busy = true;
      _input.clear();
    });
    try {
      final reply = await widget.fetcher(widget.kind, text: text, lang: lang, slots: _slots, asking: _asking);
      turn.reply = reply;
      _slots = reply.slots;
      _asking = reply.isAnswer ? null : reply.asking;
    } catch (e) {
      turn.error = e is AdvisoryError
          ? e
          : AdvisoryError(AdvisoryErrorKind.network, 'Something went wrong talking to the weather service.');
    }
    if (mounted) setState(() => _busy = false);
  }

  void _startOver() => setState(() {
    _turns.clear();
    _slots = const {};
    _asking = null;
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final about = _about(widget.kind);
    return SubPageScaffold(
      body: PageFrame(
        children: [
          PageHeader(title: about.title, subtitle: about.lead),
          const SizedBox(height: AppSpace.md),
          if (_turns.isEmpty) ...[
            const SectionTitle('Try asking'),
            const SizedBox(height: AppSpace.sm),
            for (final example in about.examples) ...[
              ActionRow(icon: about.icon, title: example, onTap: () => _send(tr(context, example))),
              const SizedBox(height: AppSpace.sm),
            ],
          ] else ...[
            for (final turn in _turns) ...[
              _Question(turn.text),
              const SizedBox(height: AppSpace.sm),
              _Reply(turn, busy: _busy && identical(turn, _turns.last)),
              const SizedBox(height: AppSpace.md),
            ],
            Align(
              alignment: Alignment.centerLeft,
              child: PillButton(icon: Icons.restart_alt, label: 'Start over', onPressed: _busy ? null : _startOver),
            ),
          ],
          const SizedBox(height: AppSpace.md),
          AppCard(
            padding: const EdgeInsets.fromLTRB(12, 4, 4, 4),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _input,
                    minLines: 1,
                    maxLines: 3,
                    textInputAction: TextInputAction.send,
                    onSubmitted: _send,
                    style: AppText.bodyMd.copyWith(color: t.onSurface),
                    decoration: InputDecoration(
                      hintText: tr(context, _asking == null ? 'Ask a question…' : 'Your answer…'),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(vertical: 14), // 48 dp tall
                    ),
                  ),
                ),
                IconButton(
                  tooltip: tr(context, 'Send'),
                  onPressed: _busy ? null : () => _send(_input.text),
                  icon: Icon(Icons.send_rounded, color: t.primary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Question extends StatelessWidget {
  final String text;
  const _Question(this.text);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Padding(
      padding: const EdgeInsets.only(left: 48),
      child: Align(
        alignment: Alignment.centerRight,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 12),
          decoration: BoxDecoration(gradient: t.accentGradient, borderRadius: BorderRadius.circular(AppRadius.xl)),
          child: Text(text, style: AppText.bodyMd.copyWith(color: t.onPrimary)),
        ),
      ),
    );
  }
}

class _Reply extends StatelessWidget {
  final _Turn turn;
  final bool busy;
  const _Reply(this.turn, {required this.busy});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final reply = turn.reply;
    final error = turn.error;
    if (error != null) {
      return ErrorPanel(
        icon: Icons.wifi_off,
        title: 'Advice unavailable',
        message: error.message,
        messageArgs: error.args,
      );
    }
    if (reply == null) return LoadingPanel(busy ? 'Checking the weather for your plan…' : '');
    if (!reply.isAnswer) {
      return AppCard(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const IconDisc(Icons.help_outline, size: 32),
            const SizedBox(width: 12),
            Expanded(
              child: Text(reply.question ?? '', style: AppText.bodyMd.copyWith(color: t.ink)),
            ),
          ],
        ),
      );
    }
    return _Answer(reply);
  }
}

/// The verdict, its reasons, the window and where it all came from.
class _Answer extends StatelessWidget {
  final AdvisoryReply reply;
  const _Answer(this.reply);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final scheme = Theme.of(context).colorScheme;
    final (String label, Color tone, IconData icon) = switch (reply.verdict) {
      'go' => ('Go', warningColor('green'), Icons.check_circle_outline),
      'suitable' => ('Suitable', warningColor('green'), Icons.check_circle_outline),
      'caution' => ('Go with caution', warningColor('orange'), Icons.warning_amber_rounded),
      'avoid' => ('Avoid', warningColor('red'), Icons.block),
      'not_suitable' => ('Not suitable', warningColor('red'), Icons.block),
      _ => ('Not available', t.onSurfaceVariant, Icons.help_outline),
    };
    final english = langOf(context) != 'en';
    final muted = AppText.bodySm.copyWith(color: t.inkMuted);
    Widget reasons(IconData icon, Color color, List<String> lines) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final line in lines)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(icon, size: 16, color: color),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(line, style: AppText.bodyMd.copyWith(color: t.onSurface)),
                ),
              ],
            ),
          ),
      ],
    );

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              IconDisc(icon, color: tone, solid: true, size: 36),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  tr(context, label),
                  // Ink, not the tone: the badge carries the colour, the text stays readable.
                  style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
          if (reply.slots.isNotEmpty) ...[
            const SizedBox(height: AppSpace.sm),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [for (final label in _slotLabels(context, reply.slots)) TagChip(label)],
            ),
          ],
          if (reply.pros.isNotEmpty) reasons(Icons.add_circle_outline, warningColor('green'), reply.pros),
          if (reply.cons.isNotEmpty) reasons(Icons.remove_circle_outline, scheme.error, reply.cons),
          if (reply.window case final w?) ...[
            const SizedBox(height: AppSpace.sm),
            Text(
              tr(context, 'Best window: {start}–{end}', {'start': w.start, 'end': w.end}),
              style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w600),
            ),
          ],
          if (english) ...[
            const SizedBox(height: AppSpace.sm),
            Text(tr(context, 'The reasons are shown in English.'), style: muted),
          ],
          if (reply.sources.isNotEmpty) ...[
            const SizedBox(height: AppSpace.sm),
            Row(
              children: [
                LiveBadge(live: reply.allLive),
                const SizedBox(width: AppSpace.sm),
                Expanded(child: Text(reply.sources.join(' · '), style: muted)),
              ],
            ),
          ],
          if (reply.disclaimer case final d?) ...[
            const SizedBox(height: AppSpace.sm),
            Text(tr(context, d), style: muted),
          ],
        ],
      ),
    );
  }
}
