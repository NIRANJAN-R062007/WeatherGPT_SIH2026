// Remembers the app's settings across launches: language, °C / °F, the
// selected city, the persona and Light / Dark / System appearance (UiPrefs).
// They are kept as one small JSON file in the app support directory, so a
// farmer who picked Farmer, Madurai and Tamil gets them back after a restart.
// Best effort: a failed read starts from the defaults, a failed write leaves
// the settings in memory only. Nothing personal is stored here; the session
// lives in the secure store (auth_store.dart).
//
// Builds before this kept only the language, in a one-line `app_language`
// file. It is read when there is no settings file yet and deleted once the
// settings file has been written.
import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Where the settings are kept between launches.
abstract class PrefsStore {
  /// The saved settings, or null when there are none or they can't be read.
  /// Values are unvalidated; UiPrefs.applySaved checks each one.
  Future<Map<String, String>?> read();
  Future<void> write(Map<String, String> prefs);
}

class FilePrefsStore implements PrefsStore {
  final Future<Directory> Function() _dir;
  FilePrefsStore({Future<Directory> Function()? dir}) : _dir = dir ?? getApplicationSupportDirectory;

  Future<File> _file(String name) async => File('${(await _dir()).path}/$name');

  @override
  Future<Map<String, String>?> read() async {
    try {
      final file = await _file('app_prefs.json');
      if (await file.exists()) {
        final json = jsonDecode(await file.readAsString());
        if (json is! Map) return null;
        return {
          for (final MapEntry(:key, :value) in json.entries)
            if (key is String && value is String) key: value,
        };
      }
      final legacy = await _file('app_language');
      if (await legacy.exists()) {
        final lang = (await legacy.readAsString()).trim();
        return lang.isEmpty ? null : {'lang': lang};
      }
    } catch (_) {
      // Unreadable — start from the defaults.
    }
    return null;
  }

  @override
  Future<void> write(Map<String, String> prefs) async {
    try {
      await (await _file('app_prefs.json')).writeAsString(jsonEncode(prefs));
      final legacy = await _file('app_language');
      if (await legacy.exists()) await legacy.delete();
    } catch (_) {
      // Not remembered — the app starts from the defaults next launch.
    }
  }
}

/// Keeps the settings in memory — widget tests.
class MemoryPrefsStore implements PrefsStore {
  Map<String, String>? saved;
  MemoryPrefsStore([this.saved]);

  @override
  Future<Map<String, String>?> read() async => saved == null ? null : Map.of(saved!);
  @override
  Future<void> write(Map<String, String> prefs) async => saved = Map.of(prefs);
}
