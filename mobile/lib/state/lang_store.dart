// Remembers the app language across launches — a one-line file in the app
// support directory — so the language picked on the Languages page before
// signing in stays the app's language after a restart. Best effort: a
// failed read or write leaves the language in memory, as before.
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class LangStore {
  final Future<Directory> Function() _dir;
  LangStore({Future<Directory> Function()? dir}) : _dir = dir ?? getApplicationSupportDirectory;

  Future<File> get _file async => File('${(await _dir()).path}/app_language');

  Future<String?> read() async {
    try {
      final f = await _file;
      if (!await f.exists()) return null;
      final lang = (await f.readAsString()).trim();
      return lang.isEmpty ? null : lang;
    } catch (_) {
      return null;
    }
  }

  Future<void> write(String lang) async {
    try {
      await (await _file).writeAsString(lang);
    } catch (_) {
      // Not remembered — the app starts in English next launch.
    }
  }
}
