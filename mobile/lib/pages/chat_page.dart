// Chat & Evidence — web/src/pages/ChatPage.tsx as a real transcript: the
// user bubble and answer card use the web page's (static-sample) bubble
// styling, every answer renders through AskAnswer with its evidence detail
// on, and the composer carries voice input (POST /asr) plus the city hint.
// Session-only, like web/: nothing here is persisted.
import 'package:flutter/material.dart';

import '../api_client.dart';
import '../components/ask_answer.dart';
import '../components/common.dart';
import '../components/composer.dart';
import '../format.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';

class _Turn {
  final String question;
  final String lang;
  final String askedAt; // IST, "13:49 IST"
  AskOutcome? outcome;
  AskError? error;
  _Turn(this.question, this.lang, this.askedAt);
  bool get pending => outcome == null && error == null;
}

List<Suggestion> _suggestions(String city) => [
      Suggestion('🌧️', 'Will it rain tomorrow in $city?'),
      Suggestion('📅', '5-day forecast for $city'),
      Suggestion('💧', 'How much rain so far today in $city?'),
      Suggestion('⚠️', 'Any weather warnings for $city?'),
    ];

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final List<_Turn> _turns = [];
  final ScrollController _scroll = ScrollController();
  final TextEditingController _query = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _scroll.dispose();
    _query.dispose();
    super.dispose();
  }

  Future<void> _ask(String text) async {
    final question = text.trim();
    if (question.isEmpty || _loading) return;
    final prefs = UiPrefs.read(context);
    final turn = _Turn(question, prefs.lang, istTime(DateTime.now().toUtc().toIso8601String()));
    setState(() {
      _turns.add(turn);
      _loading = true;
    });
    _scrollToEnd();

    try {
      turn.outcome = await askWeather(
        text: question,
        lang: prefs.lang,
        city: prefs.city,
        persona: prefs.persona,
      );
    } catch (e) {
      turn.error = e is AskError
          ? e
          : AskError(AskErrorKind.network, 'Something went wrong talking to the weather service.');
    }
    if (!mounted) return;
    setState(() => _loading = false);
    _scrollToEnd();
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    return Column(children: [
      Expanded(
        child: ListView(
          controller: _scroll,
          padding: const EdgeInsets.all(AppSpace.gutter),
          children: [
            if (_turns.isEmpty)
              _Intro(
                suggestions: _suggestions(prefs.cityInfo.name),
                onPick: (s) => _ask(s),
              )
            else ...[
              const RuleLabel(icon: Icons.bolt, text: 'Live — answers come from /ask'),
              const SizedBox(height: AppSpace.md),
              for (final turn in _turns) ...[
                _UserBubble(turn),
                const SizedBox(height: AppSpace.sm),
                _AnswerBubble(turn),
                const SizedBox(height: AppSpace.lg),
              ],
            ],
          ],
        ),
      ),
      _Dock(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          AskComposer(
            controller: _query,
            loading: _loading,
            lang: prefs.lang,
            clearOnSubmit: true,
            hint: 'Ask WeatherGPT in English, हिंदी, मराठी, தமிழ், తెలుగు…',
            onSubmit: _ask,
          ),
          const SizedBox(height: 6),
          const Padding(padding: EdgeInsets.symmetric(horizontal: 4), child: CityHintRow()),
        ]),
      ),
    ]);
  }
}

class _Intro extends StatelessWidget {
  final List<Suggestion> suggestions;
  final ValueChanged<String> onPick;
  const _Intro({required this.suggestions, required this.onPick});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const PageHeader(
        title: 'Chat & Evidence',
        subtitle: 'Every number in an answer is checked against the source data before you see it — '
            'and the evidence comes with it.',
      ),
      const SizedBox(height: AppSpace.lg),
      SurfaceCard(
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
            Text('Ask WeatherGPT', style: AppText.headlineSm.copyWith(fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: AppSpace.sm),
          Text(
            'Current conditions, a forecast, rain so far today, or IMD warnings — by text or voice, '
            'in English, हिन्दी, தமிழ், తెలుగు or मराठी.',
            style: AppText.bodyMd.copyWith(color: AppColors.onSurfaceVariant),
          ),
          const SizedBox(height: AppSpace.md),
          const MonoLabel('Suggested', color: AppColors.outline),
          const SizedBox(height: 6),
          for (final s in suggestions) ...[
            QuickQueryButton(emoji: s.emoji, text: s.text, onTap: () => onPick(s.text)),
            const SizedBox(height: 6),
          ],
        ]),
      ),
    ]);
  }
}

/// ChatPage.tsx's question bubble: primary, square bottom-right corner.
class _UserBubble extends StatelessWidget {
  final _Turn turn;
  const _UserBubble(this.turn);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 48),
      child: Align(
        alignment: Alignment.centerRight,
        child: Container(
          padding: const EdgeInsets.all(AppSpace.md),
          decoration: const BoxDecoration(
            color: AppColors.primary,
            boxShadow: AppShadows.md,
            borderRadius: BorderRadius.only(
              topLeft: Radius.circular(AppRadius.x2l),
              topRight: Radius.circular(AppRadius.x2l),
              bottomLeft: Radius.circular(AppRadius.x2l),
            ),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(
              '${turn.askedAt} · ${turn.lang.toUpperCase()}',
              style: AppText.citationMono.copyWith(color: AppColors.primaryFixed),
            ),
            const SizedBox(height: 6),
            Text(
              turn.question,
              style: AppText.bodyLg.copyWith(color: AppColors.onPrimary, fontWeight: FontWeight.w500),
            ),
          ]),
        ),
      ),
    );
  }
}

/// ChatPage.tsx's answer card: white, square bottom-left corner.
class _AnswerBubble extends StatelessWidget {
  final _Turn turn;
  const _AnswerBubble(this.turn);

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: AppSpace.sm),
      padding: const EdgeInsets.all(12),
      decoration: const BoxDecoration(
        color: AppColors.surfaceContainerLowest,
        boxShadow: AppShadows.sm,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(AppRadius.x2l),
          topRight: Radius.circular(AppRadius.x2l),
          bottomRight: Radius.circular(AppRadius.x2l),
        ),
      ),
      child: AskAnswer(
        loading: turn.pending,
        outcome: turn.outcome,
        error: turn.error,
        detail: true,
        playbackLang: turn.lang,
      ),
    );
  }
}

/// The composer pinned under the transcript.
class _Dock extends StatelessWidget {
  final Widget child;
  const _Dock({required this.child});

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppColors.surfaceContainerLowest,
        boxShadow: [BoxShadow(color: Color(0x0F000000), blurRadius: 8, offset: Offset(0, -1))],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
          child: child,
        ),
      ),
    );
  }
}
