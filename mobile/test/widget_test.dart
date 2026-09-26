import 'package:flutter_test/flutter_test.dart';

import 'package:weathergpt/main.dart';

void main() {
  testWidgets('app boots to the Ask tab with both nav destinations', (WidgetTester tester) async {
    await tester.pumpWidget(const WeatherGptApp());

    expect(find.text('Ask WeatherGPT'), findsOneWidget);
    expect(find.text('Ask'), findsOneWidget);
    expect(find.text('Warnings'), findsOneWidget);
  });
}
