// The app's own text in the app language — the one picked on the Languages
// page before signing in, or later in Settings > Language. Strings are
// written in English in the code and looked up in kUiStrings
// (ui_strings.dart, generated from ui-strings/ui_strings.json, which web/ shares);
// a string with no translation shows in English. Weather answers, condition
// labels and warning text come from the backend already in the language.
import 'package:flutter/widgets.dart';

import 'state/ui_prefs.dart';
import 'ui_strings.dart';

/// [en] in the app language, with `{name}` placeholders filled from [args].
/// Rebuilds the caller when the language changes.
String tr(BuildContext context, String en, [Map<String, Object?> args = const {}]) => trIn(langOf(context), en, args);

/// The app language, or English outside the app (widget tests).
String langOf(BuildContext context) =>
    context.dependOnInheritedWidgetOfExactType<UiPrefsScope>()?.notifier?.lang ?? 'en';

/// [en] in [lang] — for code without a BuildContext.
String trIn(String lang, String en, [Map<String, Object?> args = const {}]) =>
    fillPlaceholders(kUiStrings[lang]?[en] ?? en, args);

/// [s] with each `{name}` replaced by args[name]. Errors built away from a
/// BuildContext (the API and sign-in clients) keep their message as a table
/// key and the values in `args`, so the screen can show them in the app
/// language; their toString() fills the English.
String fillPlaceholders(String s, Map<String, Object?> args) {
  args.forEach((k, v) => s = s.replaceAll('{$k}', '${v ?? ''}'));
  return s;
}
