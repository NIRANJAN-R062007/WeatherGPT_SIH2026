// Client for the orchestrator's POST /advisory/travel and /advisory/sowing
// (services/orchestrator/main.py's _advisory(), plan.md TFA-17): a short
// dialogue. Each reply is either
// - `ask_back`: one question for the slot still missing (travel: origin,
//   destination, day; sowing: crop, district), with the slots gathered so
//   far, which the next turn sends back; or
// - `ok`: a verdict (travel: go / caution / avoid; sowing: suitable /
//   not_suitable; either: not_available), the pros and cons behind it, maybe
//   a time window, provenance per data section and a disclaimer.
// The question is in the user's language; the pros and cons are English.
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'config.dart';
import 'i18n.dart';

/// The agent may wait on an LLM and fall back to a template: /ask's budget.
const Duration kAdvisoryTimeout = Duration(seconds: 30);

enum AdvisoryKind {
  travel('/advisory/travel'),
  sowing('/advisory/sowing');

  final String path;
  const AdvisoryKind(this.path);
}

enum AdvisoryErrorKind { http, network, timeout, malformed }

class AdvisoryError implements Exception {
  final AdvisoryErrorKind kind;
  final String message;

  /// Values for the `{name}` placeholders in [message], a ui_strings.json key.
  final Map<String, Object?> args;
  AdvisoryError(this.kind, this.message, {this.args = const {}});
  @override
  String toString() => fillPlaceholders(message, args);
}

List<String> _strings(Object? v) => [
  for (final e in v is List ? v : const []) ?(e is String && e.isNotEmpty ? e : null),
];

class AdvisoryReply {
  /// "ask_back" or "ok".
  final String status;

  /// ask_back: what to ask the user, in their language.
  final String? question;

  /// The slots gathered so far (e.g. origin, destination, day, mode; crop,
  /// district): sent back with the next turn.
  final Map<String, String> slots;

  /// ask_back: the slot [question] asks for, sent back with the answer.
  final String? asking;

  /// ok: go / caution / avoid, suitable / not_suitable, or not_available.
  final String? verdict;
  final List<String> pros;
  final List<String> cons;

  /// ok: the best window, "HH:MM" city-local, when there is one.
  final ({String start, String end})? window;

  /// ok: the data sources behind the answer and whether all were live.
  final List<String> sources;
  final bool allLive;
  final String? disclaimer;

  const AdvisoryReply({
    required this.status,
    this.question,
    this.slots = const {},
    this.asking,
    this.verdict,
    this.pros = const [],
    this.cons = const [],
    this.window,
    this.sources = const [],
    this.allLive = false,
    this.disclaimer,
  });

  bool get isAnswer => status == 'ok';

  factory AdvisoryReply.fromJson(Map<String, dynamic> json) {
    final answer = json['answer'] is Map<String, dynamic> ? json['answer'] as Map<String, dynamic> : const {};
    final w = answer['window'];
    final provenance = [
      for (final p in json['provenance'] is List ? json['provenance'] as List : const [])
        if (p is Map<String, dynamic>) p,
    ];
    return AdvisoryReply(
      status: json['status'] is String ? json['status'] as String : 'ok',
      question: json['question'] as String?,
      slots: {
        if (json['slots'] is Map)
          for (final MapEntry(:key, :value) in (json['slots'] as Map).entries)
            if (key is String && value is String) key: value,
      },
      asking: json['asking'] as String?,
      verdict: answer['verdict'] as String?,
      pros: _strings(answer['pros']),
      cons: _strings(answer['cons']),
      window: w is Map && w['start_local'] is String && w['end_local'] is String
          ? (start: w['start_local'] as String, end: w['end_local'] as String)
          : null,
      sources: {for (final p in provenance) ?(p['source'] is String ? p['source'] as String : null)}.toList(),
      allLive: provenance.isNotEmpty && provenance.every((p) => p['is_live'] == true),
      disclaimer: json['disclaimer'] as String?,
    );
  }
}

/// Where advisory replies come from; tests pass a stub.
typedef AdvisoryFetcher =
    Future<AdvisoryReply> Function(
      AdvisoryKind kind, {
      required String text,
      required String lang,
      Map<String, String> slots,
      String? asking,
    });

/// One turn: [text] as typed, with the [slots] and [asking] of the last reply.
Future<AdvisoryReply> fetchAdvisory(
  AdvisoryKind kind, {
  required String text,
  required String lang,
  Map<String, String> slots = const {},
  String? asking,
}) async {
  final uri = Uri.parse('$kApiBaseUrl${kind.path}');
  final body = jsonEncode({'text': text, 'lang': lang, 'slots': slots, 'asking': ?asking});

  http.Response res;
  try {
    res = await http.post(uri, headers: {'content-type': 'application/json'}, body: body).timeout(kAdvisoryTimeout);
  } on TimeoutException {
    throw AdvisoryError(
      AdvisoryErrorKind.timeout,
      'No answer within {seconds}s — the weather service timed out.',
      args: {'seconds': kAdvisoryTimeout.inSeconds},
    );
  } catch (_) {
    throw AdvisoryError(
      AdvisoryErrorKind.network,
      "Couldn't reach the weather service at {url}. Is the orchestrator running?",
      args: {'url': kApiBaseUrl},
    );
  }
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw AdvisoryError(
      AdvisoryErrorKind.http,
      'The weather service replied HTTP {status}.',
      args: {'status': res.statusCode},
    );
  }
  try {
    return AdvisoryReply.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  } catch (_) {
    throw AdvisoryError(AdvisoryErrorKind.malformed, "The weather service's reply wasn't valid JSON.");
  }
}
