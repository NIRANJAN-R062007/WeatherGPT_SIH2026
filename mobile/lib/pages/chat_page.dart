// Chat & Evidence — the pics/ mockup: before the first question, the ask
// bar sits under the title with Suggested Questions below it; once a
// conversation starts it becomes a transcript (web/src/pages/ChatPage.tsx's
// bubbles, every answer through AskAnswer with its evidence detail on) with
// the ask bar docked at the bottom. The ask bar carries voice input (POST
// /asr). Questions handed over by other pages (ShellNav.ask) are asked on
// arrival. Session-only, like web/: nothing here is persisted.
import 'package:flutter/material.dart';

import '../api_client.dart';
import '../components/app_shell.dart';
import '../components/ask_answer.dart';
import '../components/common.dart';
import '../components/composer.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../format.dart';
import '../state/ui_prefs.dart';
import '../persona_theme.dart';
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
  ValueNotifier<String?>? _pending;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final pending = ShellNav.read(context).pendingAsk;
    if (pending == _pending) return;
    _pending?.removeListener(_takePending);
    _pending = pending..addListener(_takePending);
    // A question handed over before this page was first built.
    if (pending.value != null) WidgetsBinding.instance.addPostFrameCallback((_) => _takePending());
  }

  void _takePending() {
    final question = _pending?.value;
    if (question == null || !mounted) return;
    _pending!.value = null;
    _ask(question);
  }

  @override
  void dispose() {
    _pending?.removeListener(_takePending);
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
      turn.outcome = await askWeather(text: question, lang: prefs.lang, city: prefs.city, persona: prefs.persona);
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
    final t = PersonaTheme.of(context);
    final prefs = UiPrefs.of(context);
    final persona = prefs.personaInfo;
    final city = prefs.cityInfo.name;
    final composer = AskComposer(
      controller: _query,
      loading: _loading,
      lang: prefs.lang,
      clearOnSubmit: true,
      hint: persona.askHint,
      onSubmit: _ask,
    );

    if (_turns.isEmpty) {
      return PageFrame(
        children: [
          PageHeader(title: 'Chat & Evidence', subtitle: persona.chatLead),
          const SizedBox(height: AppSpace.lg),
          composer,
          const SizedBox(height: AppSpace.lg),
          const SectionTitle('Suggested Questions'),
          const SizedBox(height: AppSpace.sm),
          for (final q in persona.suggestions) ...[
            ActionRow(icon: q.icon, title: q.title(city), onTap: () => _ask(q.question(city))),
            const SizedBox(height: AppSpace.sm),
          ],
        ],
      );
    }

    return PageFrame(
      controller: _scroll,
      footer: SceneryFooter.none,
      dock: _Dock(child: composer),
      children: [
        Text(
          'Chat & Evidence',
          style: AppText.headlineMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: AppSpace.sm),
        const RuleLabel(icon: Icons.bolt, text: 'Live — answers come from /ask'),
        const SizedBox(height: AppSpace.md),
        for (final turn in _turns) ...[
          _UserBubble(turn),
          const SizedBox(height: AppSpace.sm),
          _AnswerBubble(turn),
          const SizedBox(height: AppSpace.lg),
        ],
      ],
    );
  }
}

/// ChatPage.tsx's question bubble: the persona's accent gradient, square
/// bottom-right corner.
class _UserBubble extends StatelessWidget {
  final _Turn turn;
  const _UserBubble(this.turn);

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Padding(
      padding: const EdgeInsets.only(left: 48),
      child: Align(
        alignment: Alignment.centerRight,
        child: Container(
          padding: const EdgeInsets.all(AppSpace.md),
          decoration: BoxDecoration(
            gradient: t.accentGradient,
            boxShadow: AppShadows.md,
            borderRadius: BorderRadius.only(
              topLeft: Radius.circular(AppRadius.x2l),
              topRight: Radius.circular(AppRadius.x2l),
              bottomLeft: Radius.circular(AppRadius.x2l),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${turn.askedAt} · ${turn.lang.toUpperCase()}',
                style: AppText.citationMono.copyWith(color: t.primaryFixed),
              ),
              const SizedBox(height: 6),
              Text(
                turn.question,
                style: AppText.bodyLg.copyWith(color: t.onPrimary, fontWeight: FontWeight.w500),
              ),
            ],
          ),
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
    final t = PersonaTheme.of(context);
    return Container(
      margin: const EdgeInsets.only(right: AppSpace.sm),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: t.card,
        border: Border.all(color: t.cardBorder),
        boxShadow: t.cardShadow,
        borderRadius: const BorderRadius.only(
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
    final t = PersonaTheme.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(color: t.sheet),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(AppSpace.gutter, AppSpace.sm, AppSpace.gutter, AppSpace.sm),
        child: child,
      ),
    );
  }
}
