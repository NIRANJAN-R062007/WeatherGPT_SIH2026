// Client for the orchestrator's GET /glossary (glossary.py, plan.md §3.1):
// the IMD warning colour words and their meanings, and the warning category
// labels, in one language, each flagged by whether a native speaker has
// reviewed it (`native_qa`). Alerts builds its colour legend from it rather
// than carry its own copy. Saved for offline use like the other replies; a
// failure of any kind gives the saved copy if there is one.
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'config.dart';
import 'response_cache.dart';

const Duration kGlossaryTimeout = Duration(seconds: 10);

class GlossaryEntry {
  final String text;

  /// A native speaker has checked this translation (always true in English).
  final bool reviewed;
  const GlossaryEntry(this.text, {required this.reviewed});
}

class Glossary {
  final Map<String, GlossaryEntry> entries;
  const Glossary(this.entries);

  static const _colours = ['green', 'yellow', 'orange', 'red'];

  /// The colour legend, green to red, as WarningLegend rows ({colour, label,
  /// meaning}); null when any colour is missing.
  List<Map<String, dynamic>>? get legend {
    final rows = <Map<String, dynamic>>[];
    for (final c in _colours) {
      final word = entries['colour_word_$c'];
      final meaning = entries['colour_$c'];
      if (word == null || meaning == null) return null;
      rows.add({'colour': c, 'label': word.text, 'meaning': meaning.text});
    }
    return rows;
  }

  /// Every legend text has had native review.
  bool get legendReviewed =>
      _colours.every((c) => entries['colour_word_$c']?.reviewed == true && entries['colour_$c']?.reviewed == true);

  factory Glossary.fromJson(Map<String, dynamic> json) {
    final raw = json['entries'];
    return Glossary({
      if (raw is Map)
        for (final MapEntry(:key, :value) in raw.entries)
          if (key is String && value is Map && value['text'] is String)
            key: GlossaryEntry(value['text'] as String, reviewed: value['native_qa'] == true),
    });
  }
}

/// Throws on a failure with nothing saved; Alerts then keeps /warnings' own
/// legend.
Future<Glossary> fetchGlossary({required String lang, ResponseCache? cache}) async {
  final params = {'lang': lang};
  final uri = Uri.parse('$kApiBaseUrl/glossary').replace(queryParameters: params);
  final (json, _) = await fetchOrSaved(cache, replyKey('/glossary', params), () async {
    final res = await http.get(uri).timeout(kGlossaryTimeout);
    if (res.statusCode != 200) throw http.ClientException('HTTP ${res.statusCode}', uri);
    return jsonDecode(res.body) as Map<String, dynamic>;
  }, useSaved: (_) => true);
  return Glossary.fromJson(json);
}
