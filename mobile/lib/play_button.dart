// Answer playback (plan.md §8 Phase 4 voice item): a speaker button next to
// a grounded /ask reply that fetches TTS audio via POST /tts and plays it.
// Mirrors the web prototype's playAnswer()/toggleAudioFor() idle <-> playing
// toggle, minus the progress ring (audioplayers exposes position but a
// simple spinner-while-loading is enough for a first mobile pass).
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';

import 'voice_client.dart';
import 'i18n.dart';

enum _PlayState { idle, loading, playing, error }

class PlayButton extends StatefulWidget {
  final String text;
  final String lang;
  const PlayButton({super.key, required this.text, required this.lang});

  @override
  State<PlayButton> createState() => _PlayButtonState();
}

class _PlayButtonState extends State<PlayButton> {
  /// Made on the first Listen rather than with every answer: each holds a
  /// native player, and most answers are never played.
  AudioPlayer? _player;
  _PlayState _state = _PlayState.idle;

  AudioPlayer get _audio => _player ??= AudioPlayer()
    ..onPlayerComplete.listen((_) {
      if (mounted) setState(() => _state = _PlayState.idle);
    });

  @override
  void dispose() {
    _player?.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    if (_state == _PlayState.loading) return;
    if (_state == _PlayState.playing) {
      await _player?.stop();
      if (mounted) setState(() => _state = _PlayState.idle);
      return;
    }
    setState(() => _state = _PlayState.loading);
    final bytes = await synthesizeSpeech(text: widget.text, lang: widget.lang);
    if (!mounted) return;
    if (bytes == null) {
      setState(() => _state = _PlayState.error);
      return;
    }
    try {
      await _audio.play(BytesSource(Uint8List.fromList(bytes)));
      if (mounted) setState(() => _state = _PlayState.playing);
    } catch (_) {
      if (mounted) setState(() => _state = _PlayState.error);
    }
  }

  @override
  Widget build(BuildContext context) {
    switch (_state) {
      case _PlayState.loading:
        return const SizedBox(
          width: 20,
          height: 20,
          child: Padding(
            padding: EdgeInsets.all(2),
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        );
      case _PlayState.error:
        return IconButton(
          tooltip: tr(context, 'Playback unavailable'),
          icon: const Icon(Icons.volume_off, size: 20),
          onPressed: () => setState(() => _state = _PlayState.idle),
        );
      case _PlayState.playing:
        return IconButton(
          tooltip: tr(context, 'Stop'),
          icon: const Icon(Icons.stop_circle, size: 20),
          onPressed: _toggle,
        );
      case _PlayState.idle:
        return IconButton(
          tooltip: tr(context, 'Listen'),
          icon: const Icon(Icons.volume_up, size: 20),
          onPressed: _toggle,
        );
    }
  }
}
