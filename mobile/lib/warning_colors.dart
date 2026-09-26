// IMD colour-code -> Material colour. plan.md §2 principle 4: the LLM/UI
// only translates and explains this colour, never re-grades severity — so
// this map is the one place colour<->meaning is decided, driven entirely by
// the feed's own `colour` field.
import 'package:flutter/material.dart';

const Map<String, Color> kWarningColors = {
  'green': Color(0xFF2E7D32),
  'yellow': Color(0xFFF9A825),
  'orange': Color(0xFFEF6C00),
  'red': Color(0xFFC62828),
};

Color warningColor(String? colour) => kWarningColors[colour] ?? const Color(0xFF757575);
