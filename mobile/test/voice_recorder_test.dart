// The silence check in front of POST /asr: a recording with nothing above
// the noise floor is dropped instead of being transcribed (the emulator's
// silent mic came back from /asr as "you", which Chat then asked).
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:weathergpt/voice_recorder.dart';

/// A mono 16-bit PCM WAV of [samples], with optional chunks before `data`.
Uint8List _wav(List<int> samples, {List<(String, List<int>)> before = const []}) {
  final out = BytesBuilder();
  void u32(int v) => out.add((ByteData(4)..setUint32(0, v, Endian.little)).buffer.asUint8List());
  void u16(int v) => out.add((ByteData(2)..setUint16(0, v, Endian.little)).buffer.asUint8List());

  out.add('RIFF'.codeUnits);
  u32(0); // size; wavPeak doesn't read it
  out.add('WAVE'.codeUnits);
  out.add('fmt '.codeUnits);
  u32(16);
  u16(1); // PCM
  u16(1); // mono
  u32(16000);
  u32(32000);
  u16(2);
  u16(16);
  for (final (id, bytes) in before) {
    out.add(id.codeUnits);
    u32(bytes.length);
    out.add(bytes);
    if (bytes.length.isOdd) out.addByte(0);
  }
  out.add('data'.codeUnits);
  u32(samples.length * 2);
  final pcm = ByteData(samples.length * 2);
  for (var i = 0; i < samples.length; i++) {
    pcm.setInt16(i * 2, samples[i], Endian.little);
  }
  out.add(pcm.buffer.asUint8List());
  return out.toBytes();
}

void main() {
  test('wavPeak is the loudest sample, either sign', () {
    expect(wavPeak(_wav([0, 3, -8, 5])), 8);
    expect(wavPeak(_wav([100, -4000, 2500])), 4000);
    expect(wavPeak(_wav([-32768])), 32768);
  });

  test('wavPeak finds data after other chunks, odd-sized ones included', () {
    final wav = _wav(
      [12, -900],
      before: [
        ('LIST', [1, 2, 3]),
        ('junk', [0, 0, 0, 0]),
      ],
    );
    expect(wavPeak(wav), 900);
  });

  test('wavPeak is 0 without a data chunk or with no samples', () {
    expect(wavPeak(Uint8List.fromList('RIFF\x00\x00\x00\x00WAVE'.codeUnits)), 0);
    expect(wavPeak(_wav([])), 0);
    expect(wavPeak(Uint8List(0)), 0);
  });

  test('an emulator-quiet recording is silent; speech is not', () {
    expect(isSilentWav(_wav(List.filled(16000, 8))), isTrue);
    expect(isSilentWav(_wav([0, 255, -255, 0])), isTrue);
    expect(isSilentWav(_wav([0, kSilentPeak, 0])), isFalse);
    expect(isSilentWav(_wav([0, 3000, -2800, 0])), isFalse);
  });
}
