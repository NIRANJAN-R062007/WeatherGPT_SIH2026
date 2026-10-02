// Mic capture for voice queries (plan.md §8 Phase 4). Records mono 16-bit
// PCM WAV at 16kHz straight from the `record` plugin — matches what
// services/orchestrator's /asr endpoint (and the web prototype's hand-rolled
// WavRecorder) already expects, so no server-side changes were needed.
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

class MicPermissionDenied implements Exception {
  @override
  String toString() => 'Microphone permission was denied.';
}

/// The loudest sample in a mono 16-bit PCM WAV, 0–32768; 0 when there is no
/// `data` chunk. Walks the RIFF chunks instead of assuming a 44-byte header.
int wavPeak(Uint8List wav) {
  final data = ByteData.sublistView(wav);
  var offset = 12; // "RIFF" <size> "WAVE"
  while (offset + 8 <= wav.length) {
    final id = String.fromCharCodes(wav, offset, offset + 4);
    final size = data.getUint32(offset + 4, Endian.little);
    final start = offset + 8;
    if (id == 'data') {
      final end = (start + size).clamp(start, wav.length);
      var peak = 0;
      for (var i = start; i + 1 < end; i += 2) {
        final v = data.getInt16(i, Endian.little).abs();
        if (v > peak) peak = v;
      }
      return peak;
    }
    offset = start + size + (size & 1);
  }
  return 0;
}

/// Peaks below this (about -42 dBFS) are silence, not speech. The Android
/// emulator's mic records peaks of about 8, and /asr transcribed that as
/// "you", which Chat then asked. Speech peaks in the thousands.
const int kSilentPeak = 256;

/// True when [wav] holds no sound worth sending to /asr.
bool isSilentWav(Uint8List wav) => wavPeak(wav) < kSilentPeak;

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
  /// captured (e.g. stop() called without a prior start()) or it was silent
  /// ([isSilentWav]).
  Future<String?> stop() async {
    final resultPath = await _recorder.stop() ?? _path;
    if (resultPath == null) return null;
    final file = File(resultPath);
    if (!await file.exists()) return null;
    final bytes = await file.readAsBytes();
    unawaited(file.delete().catchError((_) => file));
    if (bytes.isEmpty || isSilentWav(bytes)) return null;
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
