// The /ask composer used by Home, Chat and Forecast: text field + send, an
// optional mic (POST /asr via voice_recorder.dart + voice_client.dart), and
// the suggestion-chip row. Two looks, both from web/src/pages/:
//   inset: false — ChatPage/ForecastPage's form row (mic | input | send on
//                  a surface-container-low strip)
//   inset: true  — HomePage's Copilot input (mic + send inside the field)
import 'package:flutter/material.dart';

import '../persona_theme.dart';
import '../theme.dart';
import '../voice_client.dart';
import '../voice_recorder.dart';
import 'common.dart';
import '../i18n.dart';

enum _Voice { idle, listening, transcribing }

/// Tap to record, tap again to stop -> transcribe -> [onTranscript]. Mirrors
/// the web prototype's toggleMic() state machine. The recorder (and its
/// platform plugin) is only created on first use.
class MicButton extends StatefulWidget {
  final String lang;
  final bool enabled;
  final bool inset;
  final ValueChanged<String> onTranscript;

  /// The recorder and POST /asr; tests pass stubs.
  final VoiceRecorder Function() newRecorder;
  final Transcriber transcribe;

  /// A user-facing reason the last attempt produced no text; null clears it.
  final ValueChanged<String?> onNotice;

  const MicButton({
    super.key,
    required this.lang,
    required this.onTranscript,
    required this.onNotice,
    this.enabled = true,
    this.inset = false,
    this.newRecorder = VoiceRecorder.new,
    this.transcribe = transcribeAudio,
  });

  @override
  State<MicButton> createState() => _MicButtonState();
}

class _MicButtonState extends State<MicButton> {
  VoiceRecorder? _recorder;
  _Voice _voice = _Voice.idle;

  @override
  void dispose() {
    final recorder = _recorder;
    if (recorder != null) {
      if (_voice == _Voice.listening) recorder.cancel();
      recorder.dispose();
    }
    super.dispose();
  }

  Future<void> _toggle() async {
    if (_voice == _Voice.transcribing) return;
    final recorder = _recorder ??= widget.newRecorder();

    if (_voice == _Voice.listening) {
      setState(() => _voice = _Voice.transcribing);
      final audio = await recorder.stop();
      if (!mounted) return;
      if (audio == null) {
        setState(() => _voice = _Voice.idle);
        widget.onNotice(tr(context, "Didn't catch any audio — try again."));
        return;
      }
      String? notice;
      var noticeArgs = const <String, Object?>{};
      final text = await widget.transcribe(
        audioBase64: audio,
        lang: widget.lang,
        onNotice: (m, [args = const {}]) {
          notice = m;
          noticeArgs = args;
        },
      );
      if (!mounted) return;
      setState(() => _voice = _Voice.idle);
      if (text != null) {
        widget.onNotice(null);
        widget.onTranscript(text);
      } else {
        widget.onNotice(tr(context, notice ?? "Didn't catch that — try again.", noticeArgs));
      }
      return;
    }

    widget.onNotice(null);
    final lang = langOf(context);
    try {
      await recorder.start();
      if (mounted) setState(() => _voice = _Voice.listening);
    } on MicPermissionDenied {
      widget.onNotice(trIn(lang, 'Microphone permission denied — allow it in Settings to ask by voice.'));
    } catch (_) {
      widget.onNotice(trIn(lang, "Couldn't access the microphone on this device."));
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final listening = _voice == _Voice.listening;
    final busy = _voice == _Voice.transcribing;
    final Color bg = listening ? AppColors.error : Colors.transparent;
    final Color fg = listening ? AppColors.onError : t.onSurfaceVariant;
    final radius = BorderRadius.circular(AppRadius.lg);
    return Tooltip(
      message: tr(context, listening ? 'Stop recording' : 'Ask by voice'),
      child: Material(
        color: bg,
        borderRadius: radius,
        child: InkWell(
          borderRadius: radius,
          onTap: widget.enabled && !busy ? _toggle : null,
          // 48 × 48 dp: Android's minimum touch target.
          child: ConstrainedBox(
            constraints: const BoxConstraints(minWidth: kMinInteractiveDimension, minHeight: kMinInteractiveDimension),
            child: Center(
              widthFactor: 1,
              heightFactor: 1,
              child: busy
                  ? const InlineSpinner(size: 20)
                  : Icon(listening ? Icons.stop : Icons.mic_none, size: 22, color: fg),
            ),
          ),
        ),
      ),
    );
  }
}

class AskComposer extends StatefulWidget {
  final bool loading;
  final ValueChanged<String> onSubmit;
  final String hint;
  final String lang;
  final bool showMic;
  final bool inset;
  final bool clearOnSubmit;
  final TextEditingController? controller;

  /// Passed to the [MicButton]; tests pass stubs.
  final VoiceRecorder Function() newRecorder;
  final Transcriber transcribe;

  const AskComposer({
    super.key,
    required this.loading,
    required this.onSubmit,
    required this.lang,
    this.hint = 'Ask WeatherGPT…',
    this.showMic = true,
    this.inset = false,
    this.clearOnSubmit = false,
    this.controller,
    this.newRecorder = VoiceRecorder.new,
    this.transcribe = transcribeAudio,
  });

  @override
  State<AskComposer> createState() => _AskComposerState();
}

class _AskComposerState extends State<AskComposer> {
  TextEditingController? _own;
  String? _micNotice;

  TextEditingController get _controller => widget.controller ?? (_own ??= TextEditingController());

  @override
  void dispose() {
    _own?.dispose();
    super.dispose();
  }

  void _submit() {
    final q = _controller.text.trim();
    if (q.isEmpty || widget.loading) return;
    FocusScope.of(context).unfocus();
    if (_micNotice != null) setState(() => _micNotice = null);
    if (widget.clearOnSubmit) _controller.clear();
    widget.onSubmit(q);
  }

  /// A transcript goes into the field rather than straight to /ask: /asr can
  /// turn background noise into words, so the asker checks it and taps Send.
  void _fillFromVoice(String text) {
    _controller.value = TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length));
    setState(() => _micNotice = tr(context, 'Check the question, then tap Send.'));
  }

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final mic = widget.showMic
        ? MicButton(
            lang: widget.lang,
            inset: widget.inset,
            enabled: !widget.loading,
            onTranscript: _fillFromVoice,
            onNotice: (m) => setState(() => _micNotice = m),
            newRecorder: widget.newRecorder,
            transcribe: widget.transcribe,
          )
        : null;

    final field = TextField(
      controller: _controller,
      minLines: 1,
      maxLines: 4,
      textInputAction: TextInputAction.send,
      onSubmitted: (_) => _submit(),
      style: AppText.bodyMd.copyWith(color: t.onSurface),
      decoration: InputDecoration(
        hintText: tr(context, widget.hint),
        hintMaxLines: 1,
        contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 14), // 48 dp tall
      ),
    );

    final send = ValueListenableBuilder<TextEditingValue>(
      valueListenable: _controller,
      builder: (context, value, _) => _SendButton(
        loading: widget.loading,
        compact: widget.inset,
        onPressed: widget.loading || value.text.trim().isEmpty ? null : () => _submit(),
      ),
    );

    final row = widget.inset
        ? Container(
            padding: const EdgeInsets.only(left: 4, right: 6, top: 4, bottom: 4),
            decoration: BoxDecoration(color: t.surfaceContainer, borderRadius: BorderRadius.circular(AppRadius.xl)),
            child: Row(
              children: [
                Expanded(child: field),
                ?mic,
                const SizedBox(width: 4),
                send,
              ],
            ),
          )
        : Container(
            // The mockups' ask bar: sparkle, field, mic, blue send square.
            padding: const EdgeInsets.fromLTRB(12, 6, 6, 6),
            decoration: BoxDecoration(
              color: t.card,
              borderRadius: BorderRadius.circular(AppRadius.card),
              border: Border.all(color: t.cardBorder),
              boxShadow: t.cardShadow,
            ),
            child: Row(
              children: [
                Icon(Icons.auto_awesome, size: 20, color: t.primary),
                const SizedBox(width: 4),
                Expanded(child: field),
                if (mic != null) ...[mic, const SizedBox(width: 4)],
                send,
              ],
            ),
          );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        row,
        if (_micNotice != null)
          Padding(
            padding: const EdgeInsets.only(top: 6, left: 4),
            child: Text(
              _micNotice!,
              style: AppText.bodySm.copyWith(color: t.onSurfaceVariant, fontStyle: FontStyle.italic),
            ),
          ),
      ],
    );
  }
}

class _SendButton extends StatelessWidget {
  final bool loading;
  final bool compact;
  final VoidCallback? onPressed;
  const _SendButton({required this.loading, required this.compact, this.onPressed});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final radius = BorderRadius.circular(compact ? AppRadius.lg : AppRadius.xl);
    final disabled = onPressed == null;
    return Tooltip(
      message: tr(context, 'Send'),
      child: DecoratedBox(
        // The persona's accent gradient, faded while there's nothing to send.
        decoration: BoxDecoration(
          borderRadius: radius,
          boxShadow: compact ? AppShadows.sm : t.cardShadow,
          gradient: t.accentGradient,
        ),
        child: Material(
          color: disabled && !loading ? t.card.withValues(alpha: 0.4) : Colors.transparent,
          borderRadius: radius,
          child: InkWell(
            borderRadius: radius,
            onTap: onPressed,
            child: Padding(
              padding: EdgeInsets.all(compact ? 7 : 11),
              child: loading
                  ? InlineSpinner(
                      size: compact ? 18 : 20,
                      color: t.onPrimary,
                      track: t.onPrimary.withValues(alpha: 0.4),
                    )
                  : Icon(Icons.send_rounded, size: compact ? 18 : 20, color: t.onPrimary),
            ),
          ),
        ),
      ),
    );
  }
}

/// HomePage.tsx's quick-inquiry row: the quoted question + a north-east arrow.
class QuickQueryButton extends StatelessWidget {
  final String text;
  final String? emoji;
  final bool enabled;
  final VoidCallback onTap;
  const QuickQueryButton({super.key, required this.text, required this.onTap, this.emoji, this.enabled = true});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Opacity(
      opacity: enabled ? 1 : 0.6,
      child: Material(
        color: t.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          onTap: enabled ? onTap : null,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    emoji == null ? '“$text”' : '$emoji $text',
                    style: AppText.labelMd.copyWith(color: t.onSurface),
                  ),
                ),
                const SizedBox(width: AppSpace.sm),
                Icon(Icons.north_east, size: 16, color: t.outline),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class Suggestion {
  final String emoji;
  final String text;
  const Suggestion(this.emoji, this.text);
}

/// ChatPage.tsx's "SUGGESTED:" chip row. The emoji is UI only — /ask gets
/// the words.
class SuggestionChips extends StatelessWidget {
  final List<Suggestion> suggestions;
  final bool enabled;
  final ValueChanged<String> onPick;
  const SuggestionChips({super.key, required this.suggestions, required this.onPick, this.enabled = true});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          MonoLabel('Suggested:', color: t.outline),
          for (final s in suggestions) ...[
            const SizedBox(width: AppSpace.sm),
            Opacity(
              opacity: enabled ? 1 : 0.6,
              child: Material(
                color: t.surfaceContainerLow,
                borderRadius: BorderRadius.circular(999),
                child: InkWell(
                  borderRadius: BorderRadius.circular(999),
                  onTap: enabled ? () => onPick(s.text) : null,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                    child: Text('${s.emoji} ${s.text}', style: AppText.labelMd.copyWith(color: t.onSurface)),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
