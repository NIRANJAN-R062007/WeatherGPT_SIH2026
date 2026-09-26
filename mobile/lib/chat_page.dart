// Flutter chat UI wired to /ask (plan.md §8 Phase 3): GPS + text query,
// all five languages as text (Chelsea's owned item, still open at the time
// this was written).
import 'package:flutter/material.dart';

import 'api_client.dart';
import 'ask_answer.dart';
import 'cities.dart';
import 'config.dart';
import 'location.dart';

class _Turn {
  final String question;
  final AskOutcome? outcome;
  final Object? error;
  const _Turn({required this.question, this.outcome, this.error});
}

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<_Turn> _turns = [];

  String _lang = 'en';
  City? _city; // null = let the NLU extract the city from the text itself
  bool _loading = false;
  bool _locating = false;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _useMyLocation() async {
    setState(() => _locating = true);
    try {
      final city = await locateNearestCity();
      setState(() => _city = city);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Nearest registered city: ${city.name}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _loading) return;
    _controller.clear();
    setState(() {
      _turns.add(_Turn(question: text));
      _loading = true;
    });
    _scrollToEnd();

    try {
      final outcome = await askWeather(text: text, lang: _lang, city: _city?.key);
      setState(() {
        _turns[_turns.length - 1] = _Turn(question: text, outcome: outcome);
      });
    } catch (e) {
      setState(() {
        _turns[_turns.length - 1] = _Turn(question: text, error: e);
      });
    } finally {
      setState(() => _loading = false);
      _scrollToEnd();
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _controlsBar(),
        const Divider(height: 1),
        Expanded(
          child: _turns.isEmpty
              ? const Center(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Text(
                      'Ask about current conditions, a forecast, or rain so far today — '
                      'in English, Hindi, Tamil, Telugu or Marathi.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.black54),
                    ),
                  ),
                )
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(12),
                  itemCount: _turns.length,
                  itemBuilder: (context, i) => _turnWidget(_turns[i]),
                ),
        ),
        const Divider(height: 1),
        _composer(),
      ],
    );
  }

  Widget _controlsBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: Row(
        children: [
          Expanded(
            child: DropdownButtonFormField<String>(
              initialValue: _lang,
              isDense: true,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Language', isDense: true),
              items: kSupportedLanguages
                  .map((l) => DropdownMenuItem(
                        value: l,
                        child: Text(kLanguageLabels[l] ?? l, overflow: TextOverflow.ellipsis),
                      ))
                  .toList(),
              onChanged: (v) => setState(() => _lang = v ?? 'en'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: DropdownButtonFormField<String?>(
              initialValue: _city?.key,
              isDense: true,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'City', isDense: true),
              items: [
                const DropdownMenuItem<String?>(
                  value: null,
                  child: Text('Auto-detect', overflow: TextOverflow.ellipsis),
                ),
                ...kCities.map(
                  (c) => DropdownMenuItem<String?>(
                    value: c.key,
                    child: Text(c.name, overflow: TextOverflow.ellipsis),
                  ),
                ),
              ],
              onChanged: (v) => setState(() => _city = v == null ? null : cityByKey(v)),
            ),
          ),
          const SizedBox(width: 4),
          IconButton(
            tooltip: 'Use my location',
            onPressed: _locating ? null : _useMyLocation,
            icon: _locating
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.my_location),
          ),
        ],
      ),
    );
  }

  Widget _turnWidget(_Turn turn) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Container(
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primary,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            turn.question,
            style: TextStyle(color: Theme.of(context).colorScheme.onPrimary),
          ),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: turn.outcome != null
              ? AskAnswerCard(outcome: turn.outcome!)
              : turn.error != null
                  ? Container(
                      margin: const EdgeInsets.symmetric(vertical: 6),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFDECEA),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text('${turn.error}', style: const TextStyle(color: Colors.black87)),
                    )
                  : const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
        ),
      ],
    );
  }

  Widget _composer() {
    return Padding(
      padding: const EdgeInsets.all(8),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              decoration: const InputDecoration(
                hintText: 'e.g. "Will it rain in Chennai tomorrow?"',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _send(),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            onPressed: _loading ? null : _send,
            icon: const Icon(Icons.send),
          ),
        ],
      ),
    );
  }
}
