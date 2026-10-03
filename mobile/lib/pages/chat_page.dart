// Chat & Evidence — the pics/ mockup: before the first question, the ask
// bar sits under the title with Suggested Questions below it; once a
// conversation starts it becomes a transcript (web/src/pages/ChatPage.tsx's
// bubbles, every answer through AskAnswer with its evidence detail on) with
// the ask bar docked at the bottom. The ask bar carries voice input (POST
// /asr). Questions handed over by other pages (ShellNav.ask) are asked on
// arrival. The transcript is session-only, like web/; a signed-in user's
// questions are also recorded server-side, for the History page.
//
// Questions go out with the "Use my location" fix when there is one, so a
// question that names no place is answered for where the user is. A reply
// that asks "which place?" offers its places to tap, or Use my location;
// either re-asks the same question as a new turn.
import 'package:flutter/material.dart';

import '../api_client.dart';
import '../cities.dart';
import '../components/app_shell.dart';
import '../components/ask_answer.dart';
import '../components/common.dart';
import '../components/composer.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../format.dart';
import '../location.dart';
import '../state/auth_store.dart';
import '../state/ui_prefs.dart';
import '../persona_theme.dart';
import '../theme.dart';
import 'best_window_page.dart';
import '../i18n.dart';

class _Turn {
  final String question;
  final String lang;
  final String askedAt; // IST, "13:49 IST"

  /// The place tapped (or "your location") when this turn re-asks.
  final String? place;
  AskOutcome? outcome;
  AskError? error;
  _Turn(this.question, this.lang, this.askedAt, {this.place});
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

  /// [placeId] / [place]: a place tapped from a reply, asked for by ID.
  Future<void> _ask(String text, {String? placeId, String? place}) async {
    final question = text.trim();
    if (question.isEmpty || _loading) return;
    final prefs = UiPrefs.read(context);
    final auth = AuthStore.maybeRead(context);
    final turn = _Turn(question, prefs.lang, istTime(DateTime.now().toUtc().toIso8601String()), place: place);
    setState(() {
      _turns.add(turn);
      _loading = true;
    });
    _scrollToEnd();

    try {
      // A signed-in user's token makes the backend record the question to
      // their History (best-effort); a guest has none and isn't recorded.
      final token = await auth?.accessToken();
      turn.outcome = await askWeather(
        text: question,
        lang: prefs.lang,
        city: prefs.city,
        persona: prefs.persona,
        token: token,
        here: prefs.here,
        placeId: placeId,
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

  /// "Use my location" from a "which place?" reply: take a fix, keep it
  /// (and the nearest city, for the other pages), and ask [question] again.
  Future<void> _useLocationAndAsk(String question) async {
    final prefs = UiPrefs.read(context);
    final messenger = ScaffoldMessenger.maybeOf(context);
    final lang = prefs.lang;
    try {
      final here = await currentPosition();
      if (!mounted) return;
      prefs.useLocation(here.lat, here.lon, nearestCity(here.lat, here.lon, prefs.cities).city.key);
      await _ask(question, place: trIn(lang, 'Your location'));
    } on LocationDenied catch (e) {
      messenger?.showSnackBar(SnackBar(content: Text(trIn(lang, e.message))));
    }
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
    final city = tr(context, prefs.cityInfo.name);
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
          const SizedBox(height: AppSpace.md),
          InfoBanner(
            icon: Icons.schedule,
            title: "When's the best time to go outside?",
            body: 'Find the best window today or tomorrow, and compare two times.',
            onTap: () => openBestWindow(context),
          ),
          const SizedBox(height: AppSpace.lg),
          const SectionTitle('Suggested Questions'),
          const SizedBox(height: AppSpace.sm),
          for (final q in persona.suggestions) ...[
            ActionRow(
              icon: q.icon,
              title: tr(context, q.label ?? q.template, {'city': city}),
              onTap: () => _ask(tr(context, q.template, {'city': city})),
            ),
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
          tr(context, 'Chat & Evidence'),
          style: AppText.headlineMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: AppSpace.sm),
        const RuleLabel(icon: Icons.bolt, text: 'Live — answers come from /ask'),
        const SizedBox(height: AppSpace.md),
        for (final turn in _turns) ...[
          _UserBubble(turn),
          const SizedBox(height: AppSpace.sm),
          _AnswerBubble(
            turn,
            onPickPlace: (id, label) => _ask(turn.question, placeId: id, place: label),
            onUseLocation: () => _useLocationAndAsk(turn.question),
          ),
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
              if (turn.place case final place?) ...[
                const SizedBox(height: 4),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.place_outlined, size: 14, color: t.primaryFixed),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(place, style: AppText.bodySm.copyWith(color: t.primaryFixed)),
                    ),
                  ],
                ),
              ],
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
  final void Function(String placeId, String label) onPickPlace;
  final VoidCallback onUseLocation;
  const _AnswerBubble(this.turn, {required this.onPickPlace, required this.onUseLocation});

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
        onPickPlace: onPickPlace,
        onUseLocation: onUseLocation,
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
