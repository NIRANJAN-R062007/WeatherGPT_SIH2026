// IMD colour-code -> Material colour. plan.md §2 principle 4: the LLM/UI
// only translates and explains this colour, never re-grades severity — so
// this map is the one place colour<->meaning is decided, driven entirely by
// the feed's own `colour` field.
import 'package:flutter/material.dart';

// Values are web/tailwind.config.js's imd-green/-yellow/-orange/-red, so a
// band reads as the same colour on both clients.
const Map<String, Color> kWarningColors = {
  'green': Color(0xFF1E7F3C),
  'yellow': Color(0xFFC99A00),
  'orange': Color(0xFFD96A0B),
  'red': Color(0xFFB3261E),
};

Color warningColor(String? colour) => kWarningColors[colour] ?? const Color(0xFF757575);
