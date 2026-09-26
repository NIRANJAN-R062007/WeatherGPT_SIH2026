// Mic capture for voice queries (plan.md §8 Phase 4). Records mono 16-bit
// PCM WAV at 16kHz straight from the `record` plugin — matches what
// services/orchestrator's /asr endpoint (and the web prototype's hand-rolled
// WavRecorder) already expects, so no server-side changes were needed.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

class MicPermissionDenied implements Exception {
  @override
  String toString() => 'Microphone permission was denied.';
}

class VoiceRecorder {
  final AudioRecorder _recorder = AudioRecorder();
  String? _path;

  static const RecordConfig _config = RecordConfig(
    encoder: AudioEncoder.wav,
    sampleRate: 16000,
    numChannels: 1,
  );

  Future<void> start() async {
    if (!await _recorder.hasPermission()) {
      throw MicPermissionDenied();
    }
    final dir = await getTemporaryDirectory();
    _path = '${dir.path}/weathergpt_query_${DateTime.now().microsecondsSinceEpoch}.wav';
    await _recorder.start(_config, path: _path!);
  }

  /// Stops recording and returns the captured audio as base64 mono 16-bit
  /// PCM WAV, ready for POST /asr's `audio` field. Null if nothing was
  /// captured (e.g. stop() called without a prior start()).
  Future<String?> stop() async {
    final resultPath = await _recorder.stop() ?? _path;
    if (resultPath == null) return null;
    final file = File(resultPath);
    if (!await file.exists()) return null;
    final bytes = await file.readAsBytes();
    unawaited(file.delete().catchError((_) => file));
    if (bytes.isEmpty) return null;
    return base64Encode(bytes);
  }

  Future<void> cancel() async {
    try {
      await _recorder.stop();
    } catch (_) {}
    final path = _path;
    if (path != null) {
      final file = File(path);
      if (await file.exists()) unawaited(file.delete().catchError((_) => file));
    }
  }

  void dispose() {
    _recorder.dispose();
  }
}
