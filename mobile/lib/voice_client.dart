// Client for the orchestrator's POST /asr and POST /tts endpoints
// (plan.md §8 Phase 4 voice item). Mirrors the request/response contract
// prototype/frontend/WeatherGPT.dc.html already exercises against the same
// backend (services/orchestrator/main.py's ASRRequest/TTSRequest):
// /asr wants base64 mono 16-bit PCM WAV + lang + sampling_rate and returns
// {text} or {text: null, message}; /tts wants text + lang and returns
// {audio: base64 wav} or {audio: null}.
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'config.dart';

/// services/orchestrator/main.py's MAX_TTS_CHARS.
const int kMaxTtsChars = 500;

const Duration kVoiceTimeout = Duration(seconds: 20);

/// Transcribes [audioBase64] (mono 16-bit PCM WAV) via POST /asr.
/// Returns the recognized text, or null with [onNotice] called for a
/// user-facing reason (no speech, service unavailable) — mirrors the web
/// prototype's micNotice handling rather than throwing for these cases.
Future<String?> transcribeAudio({
  required String audioBase64,
  required String lang,
  int samplingRate = 16000,
  void Function(String message)? onNotice,
}) async {
  final uri = Uri.parse('$kApiBaseUrl/asr');
  http.Response res;
  try {
    res = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'audio': audioBase64,
            'lang': lang,
            'sampling_rate': samplingRate,
          }),
        )
        .timeout(kVoiceTimeout);
  } catch (_) {
    onNotice?.call("Couldn't reach the voice service.");
    return null;
  }
  if (res.statusCode < 200 || res.statusCode >= 300) {
    onNotice?.call('The voice service replied HTTP ${res.statusCode}.');
    return null;
  }
  Map<String, dynamic> payload;
  try {
    payload = jsonDecode(res.body) as Map<String, dynamic>;
  } catch (_) {
    onNotice?.call("The voice service's reply wasn't valid JSON.");
    return null;
  }
  final text = payload['text'] as String?;
  if (text == null || text.isEmpty) {
    onNotice?.call(payload['message'] as String? ?? "Didn't catch that — try again.");
    return null;
  }
  return text;
}

/// Synthesizes [text] via POST /tts. Returns raw decoded WAV bytes, or null
/// if the voice service has no credentials/failed — callers should just
/// skip playback in that case, same as the web prototype.
Future<List<int>?> synthesizeSpeech({required String text, required String lang}) async {
  final uri = Uri.parse('$kApiBaseUrl/tts');
  http.Response res;
  try {
    res = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'text': text.length > kMaxTtsChars ? text.substring(0, kMaxTtsChars) : text,
            'lang': lang,
          }),
        )
        .timeout(kVoiceTimeout);
  } catch (_) {
    return null;
  }
  if (res.statusCode < 200 || res.statusCode >= 300) return null;
  Map<String, dynamic> payload;
  try {
    payload = jsonDecode(res.body) as Map<String, dynamic>;
  } catch (_) {
    return null;
  }
  final audioB64 = payload['audio'] as String?;
  if (audioB64 == null) return null;
  try {
    return base64Decode(audioB64);
  } catch (_) {
    return null;
  }
}
