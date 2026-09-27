// Shared /ask call state for a single-answer composer — the mobile twin of
// web/src/lib/useAsk.ts: one in-flight request at a time, late replies from
// a superseded request dropped. The Chat page keeps a whole transcript
// instead and doesn't use this.
import 'package:flutter/foundation.dart';

import '../api_client.dart';

class AskController extends ChangeNotifier {
  /// The question the displayed result answers (not the live input value).
  String? asked;

  /// The language [asked] was sent in — what answer playback should use.
  String? lang;
  bool loading = false;
  AskOutcome? outcome;
  AskError? error;

  int _requestId = 0;
  bool _disposed = false;

  Future<void> ask(String text, {String? lang, String? city, String? persona}) async {
    final question = text.trim();
    if (question.isEmpty) return;

    final id = ++_requestId;
    asked = question;
    this.lang = lang;
    loading = true;
    outcome = null;
    error = null;
    notifyListeners();

    try {
      final result = await askWeather(text: question, lang: lang, city: city, persona: persona);
      if (_disposed || id != _requestId) return;
      outcome = result;
    } catch (e) {
      if (_disposed || id != _requestId) return;
      error = e is AskError
          ? e
          : AskError(AskErrorKind.network, 'Something went wrong talking to the weather service.');
    }
    loading = false;
    notifyListeners();
  }

  void reset() {
    _requestId++;
    asked = null;
    lang = null;
    loading = false;
    outcome = null;
    error = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
