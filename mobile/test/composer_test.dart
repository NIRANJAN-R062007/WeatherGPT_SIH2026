// The ask composer's mic: a transcript lands in the field for the asker to
// check, and only Send asks it (/asr can turn background noise into words).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:weathergpt/components/composer.dart';
import 'package:weathergpt/persona_theme.dart';
import 'package:weathergpt/state/ui_prefs.dart';
import 'package:weathergpt/theme.dart';
import 'package:weathergpt/voice_recorder.dart';

class _FakeRecorder implements VoiceRecorder {
  bool started = false;

  @override
  Future<void> start() async => started = true;

  @override
  Future<String?> stop() async => started ? 'UklGRg==' : null;

  @override
  Future<void> cancel() async {}

  @override
  void dispose() {}
}

void main() {
  testWidgets('a transcript fills the field; Send asks it, the mic alone does not', (tester) async {
    final prefs = UiPrefs();
    final asked = <String>[];
    await tester.pumpWidget(
      UiPrefsScope(
        prefs: prefs,
        child: MaterialApp(
          theme: buildAppTheme(personaThemeFor(prefs.persona)),
          home: Scaffold(
            body: AskComposer(
              loading: false,
              lang: 'en',
              onSubmit: asked.add,
              newRecorder: _FakeRecorder.new,
              transcribe: ({required audioBase64, required lang, samplingRate = 16000, onNotice}) async =>
                  'Will it rain in Chennai?',
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.byTooltip('Ask by voice'));
    await tester.pump();
    expect(find.byTooltip('Stop recording'), findsOneWidget);
    await tester.tap(find.byTooltip('Stop recording'));
    await tester.pump();
    await tester.pump();

    expect(asked, isEmpty);
    expect(find.widgetWithText(TextField, 'Will it rain in Chennai?'), findsOneWidget);
    expect(find.text('Check the question, then tap Send.'), findsOneWidget);

    await tester.tap(find.byTooltip('Send'));
    await tester.pump();
    expect(asked, ['Will it rain in Chennai?']);
    expect(find.text('Check the question, then tap Send.'), findsNothing);
  });
}
