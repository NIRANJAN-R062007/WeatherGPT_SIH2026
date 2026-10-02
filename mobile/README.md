# WeatherGPT — mobile (Flutter)

The Android/iOS client for WeatherGPT. It is built to look and behave like
the web frontend in [`../web/`](../web/): same app shell (Sidebar + Topbar),
same page set, same Material 3 palette, type scale and fonts. Every screen
reads live data from the orchestrator (`services/orchestrator/`) — nothing on
screen is a static sample.

## Running it

Requires Flutter 3.47.x (Dart ≥ 3.11).

```bash
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=https://3-108-52-61.sslip.io
```

In debug and profile builds `API_BASE_URL` defaults to `http://localhost:8001`
(`lib/config.dart`), which only works on a desktop target. On a phone, pass
the deployed host above; on an Android emulator talking to a local
orchestrator, use `http://10.0.2.2:8001`. A release build defaults to the
deployed host, `https://3-108-52-61.sslip.io`, and refuses to start with a
non-https URL.

```bash
flutter analyze                     # lints
flutter test                        # widget tests (HTTP is stubbed to 400 by flutter_test)
```

## Release builds

One command, from `mobile/`:

```bash
tool/build_release.sh               # APK: build/app/outputs/flutter-apk/app-release.apk
tool/build_release.sh appbundle     # AAB for Play: build/app/outputs/bundle/release/app-release.aab
```

It runs `flutter build <apk|appbundle> --release
--dart-define=API_BASE_URL=https://3-108-52-61.sslip.io`; set `API_BASE_URL=…`
in the environment to point it elsewhere. On Windows, run that `flutter build`
line directly.

**Signing.** `android/app/build.gradle.kts` signs release builds with the
upload key described in `android/key.properties`. Without that file it falls
back to the debug key and Gradle prints a warning. A debug-signed APK installs
and runs, but Play won't accept it. The keystore and `key.properties` are made
by the app owner (Chelsea) and never committed: `key.properties`, `*.jks` and
`*.keystore` are in `android/.gitignore`. The format is:

```properties
# mobile/android/key.properties
storePassword=<keystore password>
keyPassword=<key password>
keyAlias=upload
# Relative to android/app/, or an absolute path
storeFile=../upload-keystore.jks
```

One way to create the keystore (keep it, and its passwords, out of the repo
and backed up — losing it means you can't publish updates):

```bash
keytool -genkey -v -keystore upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

**Name, icon and splash.** The app is called "WeatherGPT" (`android:label`,
iOS `CFBundleDisplayName` / `CFBundleName`). The launcher icon and the native
splash are generated from the logo marks by `flutter_launcher_icons` and
`flutter_native_splash`. Their config is at the end of `pubspec.yaml`. After
changing it, re-run `dart run flutter_launcher_icons` and
`dart run flutter_native_splash:create`. The splash tool re-indents
`ios/Runner/Info.plist` and adds `UIStatusBarHidden`; keep only the changes
you actually want.

## How the app maps to web/

| web/ page | Mobile page | Backend calls |
|---|---|---|
| `HomePage.tsx` | **Home** — current-conditions hero (condition/time-of-day gradient), humidity / wind / rain-chance / UV tiles, Today · Tonight · Tomorrow strip, feature tiles, WeatherGPT Copilot ask box | `GET /facts` ×4, `GET /ask` |
| `ChatPage.tsx` | **Chat & Evidence** — a real transcript; answers show the grounding badge, per-figure evidence and provenance; voice input and a Listen button | `GET /ask`, `POST /asr`, `POST /tts` |
| `ForecastPage.tsx` | **Forecast** — Today / Tonight / Tomorrow accordion, provenance card, forecast ask box ("5-day forecast for …") | `GET /facts`, `GET /ask` |
| `AlertsPage.tsx` | **Alerts & Warnings** — the IMD colour verdict with its legend; "no verdict" is always neutral, never green | `GET /warnings` |
| `SettingsPage.tsx` | **Settings** — language, °C/°F, persona (sent to `/ask`) | — |
| `HistoryPage.tsx` | **History** (drawer) — the signed-in user's past questions and answers; All / Alerts / Rain filters, search, "Ask again", "Clear history"; a guest is invited to sign in | `GET /history`, `DELETE /history` |

The shell is `lib/components/app_shell.dart`: on phones the Sidebar is a
drawer behind the Topbar's menu button; at ≥ 1000 px it is the permanent
256 px sidebar, like web/. The Topbar's city pill sets the city every page
uses and offers "Use my location" (nearest supported city, with a note saying
which city and how far away, and a warning beyond 50 km). The bell opens
Alerts. Android back returns to Home before leaving the app.

Only data some endpoint actually serves is shown. The web pages' static design
samples are left out: hourly chart, 10-day list, sunrise/sunset panel, "rain so
far today" tile, "Recently asked", alert category tiles, emergency hotlines and
adjacent sectors. The report below lists what each one would need.

## Code layout

```
lib/
  main.dart                 app root: UiPrefs + WeatherStore scopes, theme, page registry
  theme.dart                colours / type / spacing / radii / shadows copied from web/tailwind.config.js
  format.dart               IST timestamps, city/day labels, condition -> icon/accent
  components/
    app_shell.dart          Sidebar, Topbar, page switching (lazy IndexedStack + TickerMode)
    ask_answer.dart         renders every /ask branch (port of web AskAnswer.tsx), WarningLegend
    composer.dart           ask box, MicButton (record -> /asr), suggestion chips
    common.dart             cards, chips, badges, loading/error panels, city picker sheet
  pages/                    home, chat, forecast, alerts, settings
  state/
    ui_prefs.dart           language, unit, city, persona, appearance (web UiPrefsContext.tsx)
    prefs_store.dart        remembers ui_prefs across launches (app_prefs.json)
    weather_store.dart      shared /facts load for Home + Forecast
    ask_controller.dart     single-answer /ask state (web useAsk.ts)
  api_client.dart           GET /ask + classifyAsk (web api.ts)
  facts_client.dart         GET /facts
  warnings_client.dart      GET /warnings
  history_client.dart       GET / DELETE /history (bearer token)
  voice_client.dart         POST /asr, POST /tts
  voice_recorder.dart       16 kHz mono WAV capture (record plugin)
  play_button.dart          TTS playback (audioplayers)
  location.dart, cities.dart  GPS -> nearest of the registered cities (+ distance)
  cities_client.dart        GET /cities at start-up; bundled list as fallback
  warning_colors.dart       IMD band colours (same values as web's imd-* tokens)
assets/fonts/               static TTF weights of web/public/fonts/*.woff2 (Inter,
                            Plus Jakarta Sans, JetBrains Mono)
```

---

## Status report: what the app still needs to reach its full potential

As of 2026-09-27. Each item says what is missing, why it matters, and where
the work sits:

- **App** — mobile/ only.
- **Backend** — `services/orchestrator/`.
- **Accounts** — an external service or credential.

### P0 — before putting it in users' hands

1. **Redeploy the backend from `main`.** *(Backend / infra)* The deployed host
   (`3-108-52-61.sslip.io`) is behind `main`:
   - `/warnings` has no `status` or `legend` fields, and the warnings feed is
     off, so every city shows "No warning verdict".
   - `/facts` has no `uv_band`.
   - The unsupported-city reply lists only 3 cities, while the app offers 8.

   The app tolerates all of this, but users see less than `main` can serve.
2. **Verify on a real device.** *(App)* Everything was checked with `flutter
   analyze`, widget tests, a release APK build and rendered screenshots, but
   not on a phone or emulator (none was available). Still to exercise:
   - mic → `/asr` round trip, including the permission prompt
   - `/tts` playback
   - GPS permission flow
   - keyboard and safe-area insets on small screens
   - Hindi / Tamil / Telugu / Marathi rendering through system fonts
3. **Ship the backend URL with the build.** *(App)* Release builds must pass
   `--dart-define=API_BASE_URL=…`, or `lib/config.dart`'s default must change to
   the production host. Prefer HTTPS: the Android manifest declares no
   cleartext or network-security config, so a plain-`http://` backend (e.g. a
   LAN dev server) should be tested on-device before relying on it.
4. **Release identity.** *(App + Accounts)*
   - The Android label is `weathergpt`; the iOS display name is `Weathergpt`.
   - The launcher icon and splash are the Flutter defaults.
   - `android/app/build.gradle.kts` signs release builds with the **debug
     key**.

   Play Store / TestFlight needs a real app name, icon, splash, an upload
   keystore and an Apple signing team.
5. **Android toolchain upgrades.** *(App)* `flutter build apk` warns that
   support will soon be dropped for the versions in `android/`:
   - Gradle 8.14.0 → at least 9.1.0 (`gradle/wrapper/gradle-wrapper.properties`)
   - Android Gradle Plugin 8.11.1 → at least 9.0.1 (`settings.gradle.kts`)
   - Kotlin 2.2.20 → at least 2.3.20 (`settings.gradle.kts`)

### P1 — backend features the app doesn't use yet

6. ~~**Sign-in and History.**~~ ✅ Done. Email and Google sign-in, the
   Profile page, Chat sending `Authorization: Bearer <token>` on `/ask` (so
   the backend records a signed-in user's questions) and the History page
   (2026-10-03). Not yet checked on a device against the live Supabase project.
7. **Push alerts.** *(App + Backend + Accounts)* `POST /alerts/subscribe`
   accepts `channel: "fcm"` with a `city_key` or `lat`/`lon`/`radius_km`, but
   `alert_engine._dispatch_fcm` is still a logged no-op. Needs:
   - A Firebase project (`google-services.json` / `GoogleService-Info.plist`).
   - `firebase_messaging` in the app, subscribing with the FCM token and
     unsubscribing on opt-out, behind a Settings → Notifications toggle.
   - Backend: FCM HTTP v1 dispatch with a service account, and
     `ALERT_ENGINE_ENABLED` turned on.
8. ~~**Live city list.**~~ ✅ Done (2026-10-03). The app fetches `GET /cities`
   at start-up and offers exactly the cities that server answers for; the
   bundled list in `lib/cities.dart` is the fallback when it can't be reached.
   A selected city the server doesn't serve moves to its first city. City names
   are still translated by the app's own string table, so a city the server
   adds shows in English until `ui-strings/ui_strings.json` has it.
9. **Localized glossary.** *(App)* `GET /glossary?lang=` returns the warning
   colour words and category labels per language, with `native_qa` flags. Use
   it for the legend and labels, and mark translations that haven't had native
   review.

### P2 — plan.md commitments not yet in the app

10. **Offline-degradable** (plan.md §2 principle 5). *(App)* Every screen
    currently needs the network. Needs:
    - Cache the last-known `/facts`, `/warnings` and recent answers on device.
    - Show "cached at HH:MM IST" when offline, with connectivity detection.
    - Packages: e.g. `shared_preferences` or `hive`, plus `connectivity_plus`.
11. ~~**Persist preferences.**~~ ✅ Done (2026-10-03). Language, °C / °F, city,
    persona and Light / Dark / System are saved to a small JSON file in the app
    support directory (`lib/state/prefs_store.dart`) and restored at launch;
    the older language-only file is migrated. No new package was needed.
12. **Localize the app's own UI.** *(App)* Answers come back localized from the
    backend, but the app's labels, buttons and headings are English only. Add
    `flutter_localizations` with ARB files for hi / ta / te / mr (native review
    needed, as for the backend strings).
13. **Cyclone map** (plan.md §8, open). *(App + Backend)* Needs a map package
    (`flutter_map` with OSM tiles, or `google_maps_flutter`) and a source of
    cyclone tracks / CAP warning polygons. `imd_warnings.py` is a per-city
    fixture with no geometry yet.
14. **Real location queries.** *(Backend, then App)* The backend only accepts a
    city, so "Use my location" snaps to the nearest registered city (it now
    says which and how far, and warns beyond 50 km). Google
    Weather is lat/lon-based, so `/ask` and `/facts` could take `lat`/`lon`
    directly.

### P3 — web design sections that need new endpoints first

15. **Hourly forecast** strip and chart. *(Backend, then App)* Needs an hourly
    endpoint backed by Google Weather's hourly forecast.
16. **Structured 5–10 day list.** *(Backend, then App)*
    `weather_data.multi_day_facts()` exists but only reaches clients as narrated
    `/ask` text. A `GET /forecast?city=&days=` would let the app render web's
    10-day accordion from real figures.
17. **Sunrise / sunset / daylight progress** (web Home hero). *(Backend, then
    App)* Google Weather's `forecastDays` carry sun events, but `/facts` doesn't
    expose them. The hero's time-of-day tint uses web's fixed 06:32 / 18:14
    until then.
18. **"Rain so far today" tile.** *(Backend, then App)*
    `weather_data.rain_so_far()` exists, but only `/ask` reaches it. Expose it
    on `/facts`.
19. **Emergency hotlines** (web Alerts sample). *(Content)* Needs a verified,
    city-aware list before any phone number ships.

### P4 — engineering hygiene

20. **CI job for mobile/.** `.github/workflows/ci.yml` has none. Add
    `flutter analyze`, `flutter test` and `flutter build apk`.
21. **Better tests.** Widget tests run against flutter_test's stub HTTP (every
    call returns 400), so they cover error paths and layout only. `AskAnswer` is
    fixture-tested per branch. Still needed:
    - An injectable HTTP client with fixture-backed success-path tests per page.
    - An `integration_test` run on a device.
22. **Web target.** There is no `web/` platform folder. `flutter create
    --platforms web .` builds cleanly (checked in a scratch copy), but voice
    input would not work there: `voice_recorder.dart` writes a temp file through
    `dart:io` and `path_provider`. Web users are served by `../web/` anyway.
23. **Indic fonts.** The app relies on Android/iOS system fonts for
    Devanagari, Tamil and Telugu. web/ bundles Noto subsets. Bundle them here
    too if older devices show missing glyphs.
24. **Accessibility pass.** Check large text scale, and TalkBack / VoiceOver
    on the icon-only controls (most carry tooltips).

### Known limits that are not app bugs

- `warning.advice` stays English in every language — it's the feed's own text
  (plan.md audit 4.3).
- The °C / °F setting converts dashboard figures only; narrated answers keep
  the units the backend writes.
