// AskAnswer against one body per /ask branch — shapes as documented in
// web/src/lib/api.ts (captured from a live orchestrator) and
// services/orchestrator/main.py's ask().
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/api_client.dart';
import 'package:weathergpt/components/ask_answer.dart';
import 'package:weathergpt/theme.dart';
import 'package:weathergpt/warning_colors.dart';

const _nlu = {
  'intent': 'current_weather',
  'city': 'Chennai',
  'time_window': 'now',
  'days': null,
  'parameter': 'all',
  'language': 'en',
  'source': 'rules',
  'confidence': 1.0,
};

const _legend = [
  {'colour': 'green', 'label': 'Green', 'meaning': 'No warning'},
  {'colour': 'yellow', 'label': 'Yellow', 'meaning': 'Be aware'},
  {'colour': 'orange', 'label': 'Orange', 'meaning': 'Be prepared'},
  {'colour': 'red', 'label': 'Red', 'meaning': 'Take action'},
];

Map<String, dynamic> _grounding({bool ok = true}) => {
      'ok': ok,
      'matched': ok ? 2 : 1,
      'total': 2,
      'figures': [
        {'reading': '34°C', 'value': 34, 'unit': 'c', 'path': 'temp_c', 'matched': true},
        {'reading': '54%', 'value': 54, 'unit': '%', 'path': ok ? 'humidity_pct' : null, 'matched': ok},
      ],
      'fallback_used': false,
      'narration': 'llm',
      'attempts': 1,
      'provider': 'gemini',
    };

const _provenance = {
  'source': 'Google Weather API (live)',
  'issued': '2026-09-27T08:19:15Z',
  'is_live': true,
  'retrieved_at': '2026-09-27T08:20:00Z',
};

Future<void> _pump(WidgetTester tester, Map<String, dynamic> body, {bool detail = true}) {
  return tester.pumpWidget(MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(
      body: SingleChildScrollView(
        child: AskAnswer(asked: 'q', outcome: classifyAsk(body), detail: detail),
      ),
    ),
  ));
}

bool _paintsColour(WidgetTester tester, Color colour) => tester
    .widgetList<Container>(find.byType(Container))
    .any((c) => c.decoration is BoxDecoration && (c.decoration as BoxDecoration).color == colour);

void main() {
  testWidgets('success: grounded badge, chips, evidence and provenance', (tester) async {
    await _pump(tester, {
      'intent': 'current_weather',
      'city': 'chennai',
      'day': 'today',
      'response': 'It is 34°C in Chennai with 54% humidity.',
      'provenance': _provenance,
      'grounding': _grounding(),
      'nlu': _nlu,
    });
    expect(find.text('GROUNDED 2/2'), findsOneWidget);
    expect(find.text('CURRENT WEATHER'), findsOneWidget);
    expect(find.text('Chennai'), findsOneWidget);
    expect(find.text('It is 34°C in Chennai with 54% humidity.'), findsOneWidget);
    expect(find.text('34°C'), findsOneWidget); // figure chip, detail on
    expect(find.text('LIVE'), findsOneWidget);
    expect(find.text('Issued 27 Sep, 13:49 IST'), findsOneWidget);
  });

  testWidgets('warnings: verdict colour, verbatim headline, legend', (tester) async {
    await _pump(tester, {
      'intent': 'warnings',
      'city': 'chennai',
      'response': 'Heavy rain likely at isolated places.',
      'status': 'active',
      'warning': {
        'city': 'chennai',
        'district': 'Chennai',
        'colour': 'orange',
        'colour_label': 'Orange',
        'category': 'heavy_rain',
        'category_label': 'Heavy rain',
        'headline': 'Heavy rain likely at isolated places.',
        'advice': 'Avoid low-lying areas.',
        'disclaimer': 'Simulated data — pending official feed access',
        'valid_from': '2026-09-27T00:00:00Z',
        'valid_to': '2026-09-28T00:00:00Z',
        'issued_by': 'IMD Chennai',
        'source': 'fixture',
      },
      'legend': _legend,
      'provenance': {
        'source': 'fixture',
        'issued_by': 'IMD Chennai',
        'valid_from': '2026-09-27T00:00:00Z',
        'valid_to': '2026-09-28T00:00:00Z',
        'is_live': false,
        'retrieved_at': '2026-09-27T08:20:00Z',
      },
      'grounding': {
        'ok': true, 'matched': 0, 'total': 0, 'figures': [],
        'fallback_used': false, 'narration': 'verbatim', 'attempts': 0, 'provider': 'feed',
      },
      'nlu': _nlu,
    });
    expect(find.text('Orange — in force'), findsOneWidget);
    expect(find.text('Heavy rain likely at isolated places.'), findsOneWidget);
    expect(find.text('Avoid low-lying areas.'), findsOneWidget);
    expect(find.text('FIXTURE'), findsOneWidget);
    // Phase 7 B2: every fixture-sourced warning card carries this label.
    expect(find.text('Simulated data — pending official feed access'), findsOneWidget);
    expect(_paintsColour(tester, warningColor('orange')), isTrue);
  });

  testWidgets('warnings: no disclaimer field (older orchestrator) renders with no gap', (tester) async {
    await _pump(tester, {
      'intent': 'warnings',
      'city': 'chennai',
      'response': 'Heavy rain likely at isolated places.',
      'status': 'active',
      'warning': {
        'city': 'chennai',
        'district': 'Chennai',
        'colour': 'orange',
        'colour_label': 'Orange',
        'category': 'heavy_rain',
        'category_label': 'Heavy rain',
        'headline': 'Heavy rain likely at isolated places.',
        'advice': 'Avoid low-lying areas.',
        'valid_from': '2026-09-27T00:00:00Z',
        'valid_to': '2026-09-28T00:00:00Z',
        'issued_by': 'IMD Chennai',
        'source': 'fixture',
      },
      'legend': _legend,
      'provenance': {
        'source': 'fixture',
        'issued_by': 'IMD Chennai',
        'valid_from': '2026-09-27T00:00:00Z',
        'valid_to': '2026-09-28T00:00:00Z',
        'is_live': false,
        'retrieved_at': '2026-09-27T08:20:00Z',
      },
      'grounding': {
        'ok': true, 'matched': 0, 'total': 0, 'figures': [],
        'fallback_used': false, 'narration': 'verbatim', 'attempts': 0, 'provider': 'feed',
      },
      'nlu': _nlu,
    });
    expect(find.textContaining('Simulated data'), findsNothing);
  });

  testWidgets('warnings unavailable is neutral — never green', (tester) async {
    await _pump(tester, {
      'intent': 'warnings',
      'city': 'chennai',
      'message': "Warnings aren't available right now.",
      'status': 'unavailable',
      'warning': null,
      'legend': _legend,
      'nlu': _nlu,
    }, detail: false);
    expect(find.text('No warning verdict'), findsOneWidget);
    expect(find.text('STATUS: UNAVAILABLE'), findsOneWidget);
    expect(_paintsColour(tester, warningColor('green')), isFalse);
  });

  testWidgets('ungrounded: answer withheld, unmatched figure shown', (tester) async {
    await _pump(tester, {
      'intent': 'current_weather',
      'city': 'chennai',
      'message': "I couldn't verify that answer against the data.",
      'provenance': _provenance,
      'grounding': _grounding(ok: false),
      'nlu': _nlu,
    });
    expect(find.text('Answer withheld — not grounded'), findsOneWidget);
    expect(find.text('1/2 figures matched'), findsOneWidget);
    expect(find.text('54%'), findsOneWidget);
  });

  testWidgets('fallback: unsupported city keeps the rejected name', (tester) async {
    await _pump(tester, {
      'intent': 'unsupported_city',
      'message': "I don't have data for that city yet.",
      'nlu': {..._nlu, 'intent': 'unsupported_city', 'city': 'Kolkata'},
      'notice': 'Answering in English.',
    });
    expect(find.text('No answer'), findsOneWidget);
    expect(find.text('UNSUPPORTED CITY'), findsOneWidget);
    expect(find.text('asked about “Kolkata”'), findsOneWidget);
    expect(find.text('Answering in English.'), findsOneWidget);
  });

  testWidgets('transport error gets its own titled panel', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: buildAppTheme(),
      home: Scaffold(
        body: AskAnswer(error: AskError(AskErrorKind.timeout, 'No answer within 30s.')),
      ),
    ));
    expect(find.text('Request timed out'), findsOneWidget);
    expect(find.text('No answer within 30s.'), findsOneWidget);
  });
}
