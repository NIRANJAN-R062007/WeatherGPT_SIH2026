# WeatherGPT — mobile (Flutter)

The Android/iOS client for WeatherGPT. It is built to look and behave like
the web frontend in [`../web/`](../web/): same app shell (Sidebar + Topbar),
same page set, same Material 3 palette, type scale and fonts. Every screen
reads live data from the orchestrator (`services/orchestrator/`) — nothing on
screen is a static sample.

## Running it

Requires Flutter 3.47.x (Dart ≥ 3.12; `record` 7 needs it).

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
| `HomePage.tsx` | **Home** — current-conditions hero (condition/time-of-day gradient), humidity / wind / rain-chance tiles, rain so far today and daylight (sunrise, sunset, how much of the day has passed) cards, five-day strip, feature tiles, Quick Actions | `GET /facts` ×4, `GET /forecast/daily`, `GET /ask` |
| `ChatPage.tsx` | **Chat & Evidence** — a real transcript; answers show the grounding badge, per-figure evidence and provenance; voice input (the transcript fills the ask box, and Send asks it) and a Listen button | `GET /ask`, `POST /asr`, `POST /tts` |
| `ForecastPage.tsx` | **Forecast** — Days: up to 10 days (5 from fixtures), tap a day for its rain chance and millimetres, wind, humidity, UV, daylight, sunrise / sunset and night; Hourly: the next 24 hours under a temperature curve; provenance card. Against a backend without `/forecast/*` it falls back to Today / Tonight / Tomorrow from `/facts` and a "5-day forecast" question for Chat | `GET /forecast/daily`, `GET /forecast/hourly`, `GET /facts`, `GET /ask` |
| `AlertsPage.tsx` | **Alerts & Warnings** — the IMD colour verdict with its legend; "no verdict" is always neutral, never green; the city's emergency numbers (112 first), tap to open the dialer, with the date they were checked; 112 alone when the list can't be had | `GET /warnings`, `GET /hotlines` |
| `SettingsPage.tsx` | **Settings** — language, °C/°F, persona (sent to `/ask`) | — |
| `HistoryPage.tsx` | **History** (drawer) — the signed-in user's past questions and answers; All / Alerts / Rain filters, search, "Ask again", "Clear history"; a guest is invited to sign in | `GET /history`, `DELETE /history` |

The shell is `lib/components/app_shell.dart`: on phones the Sidebar is a
drawer behind the Topbar's menu button; at ≥ 1000 px it is the permanent
256 px sidebar, like web/. The Topbar's city pill sets the city every page
uses and offers "Use my location" (nearest supported city, with a note saying
which city and how far away, and a warning beyond 50 km). The bell opens
Alerts. Android back returns to Home before leaving the app.

Only data some endpoint actually serves is shown. The web pages' static design
samples that still have no endpoint are left out: "Recently asked", alert
category tiles and adjacent sectors.

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
    weather_store.dart      shared /facts + /forecast/daily + /forecast/hourly load for Home + Forecast
    ask_controller.dart     single-answer /ask state (web useAsk.ts)
  api_client.dart           GET /ask + classifyAsk (web api.ts)
  facts_client.dart         GET /facts, /forecast/daily, /forecast/hourly
  warnings_client.dart      GET /warnings
  hotlines_client.dart      GET /hotlines (112 as the fallback)
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

As of 2026-10-03. Each item says what is missing, why it matters, and where
the work sits:

- **App** — mobile/ only.
- **Backend** — `services/orchestrator/`.
- **Accounts** — an external service or credential.

### P0 — before putting it in users' hands

1. **Redeploy the backend from `main`.** *(Backend / infra — Niranjan, plan.md
   B4; runbook in `deploy/README.md`)* The deployed host
   (`3-108-52-61.sslip.io`) is an old build. `python deploy/smoke.py
   https://3-108-52-61.sslip.io --skip-ask` on 2026-10-03: `/health` passes, the
   other 6 checks fail:
   - `/cities` serves 3 cities (Chennai, Madurai, Coimbatore), not 8, and
     `/facts?city=mumbai` answers "I can only answer for Chennai, Madurai and
     Coimbatore". Since the app takes its city list from `/cities`, it offers
     only those 3 until the redeploy.
   - `/warnings` has no `status` or `legend` (`{"city", "city_name",
     "warning": null}`), so every city shows "No warning verdict".
   - `/aviation`, `/intelligence/best-window` and `/glossary` are 404, so
     Airport weather and Best Time & What-if show their error states.
   - `/forecast/daily`, `/forecast/hourly` and `/hotlines` are 404 and `/facts`
     has no `rain_so_far` (2026-10-03), so Forecast shows Today / Tonight /
     Tomorrow, Hourly says the service doesn't serve it yet, Home has no rain or
     daylight card, and Alerts lists 112 alone.

   The app tolerates all of this, but users see less than `main` can serve.
2. **Verify on a real device.** *(App)* Partly done on an Android 16 (API 36)
   emulator on 2026-10-03, against the deployed host:
   - ✅ The release APK shows the "WeatherGPT" label, icon and splash, and a
     live Home, with no `--dart-define`.
   - ✅ A restart keeps language, city, °F, persona and dark mode.
   - ✅ "Use my location": the permission prompt, the near note ("about 4 km")
     and the far note ("about 1755 km"). Driven with `adb shell cmd location
     providers` test locations; `adb emu geo fix` didn't move this emulator.
   - ✅ With no fix and nothing cached (test providers that never report, and
     Play services force-stopped to drop its cached location), "Use my
     location" stops after the 15 s limit and says "Couldn't get a location
     fix in time…", in English and in Hindi; the city is unchanged.
   - ✅ The mic permission prompt, recording, and the `/asr` round trip; a
     silent recording now says "Didn't catch any audio" instead of being
     asked. Listen played `/tts` audio (about 4 s, not listened to).
   - ✅ Hindi / Tamil / Telugu / Marathi render through system fonts; the
     bottom-bar labels now fit on one line in Tamil.
   - ✅ Safe areas at 360 × 640 dp.
   - ✅ Airport weather is in the drawer only for the Aviation persona.

   Still to check, ideally on a phone:
   - sign in (email and Google) → ask in Chat → History → Clear history,
     against the live Supabase project (needs a real account)
   - the mic with real speech, and hearing the `/tts` playback
   - the soft keyboard on a small screen (it never appeared on the emulator)
   - after the redeploy (item 1): 8 cities, Alerts, Airport weather (Aviation
     persona), Best Time & What-if, and the forecast detail (items 15–19)
   - tapping an emergency number on a real phone (on the emulator it opens the
     dialer with the number filled in)
3. ~~**Ship the backend URL with the build.**~~ ✅ Done (2026-10-03). A release
   build defaults to `https://3-108-52-61.sslip.io` (`lib/config.dart`); debug
   and profile builds keep `http://localhost:8001`. `--dart-define=API_BASE_URL=…`
   still overrides, and a release build refuses a non-https URL.
4. **Release identity.** *(App + Accounts)* Partly done (2026-10-03):
   - ✅ The app is "WeatherGPT" on Android and iOS.
   - ✅ The launcher icon and native splash are generated from the logo marks
     (see "Release builds" above).
   - ✅ `android/app/build.gradle.kts` signs release builds with the upload key
     from `android/key.properties`, and `tool/build_release.sh` is the
     one-command build.
   - Still open: the upload keystore itself (Chelsea creates it; until then
     release builds are signed with the **debug key**, and the upload-key path
     has not been exercised), an Apple signing team, and a Mac for iOS
     builds. Play Store / TestFlight need all of those.
5. ~~**Android toolchain upgrades.**~~ ✅ Done (2026-10-03): Gradle 9.3.1,
   Android Gradle Plugin 9.1.0 and Kotlin 2.4.0, the versions Flutter 3.47.2's
   app template uses. `app/build.gradle.kts` sets the JVM target through
   `kotlin { compilerOptions }`. The "support will soon be dropped" warnings
   are gone. The Kotlin Gradle Plugin warnings are gone too: the app's build
   script no longer applies `kotlin-android` (as in the 3.47 template), and
   `audioplayers` 6.8.1 / `record` 7.1.1 ship Android plugins that don't
   either. `gradle.properties` keeps `android.builtInKotlin=false` and
   `android.newDsl=false`, like Flutter 3.47's own template; with that flag
   the Flutter Gradle Plugin applies Kotlin itself. AGP notes the flag is
   deprecated, so drop it when Flutter's template does.

### P1 — backend features the app doesn't use yet

6. ~~**Sign-in and History.**~~ ✅ Done. Email and Google sign-in, the
   Profile page, Chat sending `Authorization: Bearer <token>` on `/ask` (so
   the backend records a signed-in user's questions) and the History page
   (2026-10-03). Not yet checked on a device against the live Supabase project
   (item 2).
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
   adds shows in English until `ui-strings/ui_strings.json` has it. "Use my
   location" says which city it picked and how far away it is, and warns beyond
   50 km.
9. **Localized glossary.** *(App)* `GET /glossary?lang=` returns the warning
   colour words and category labels per language, with `native_qa` flags. The
   app doesn't call it yet; the Alerts legend comes from `/warnings`' `legend`.
   Use it for the legend and labels, and mark translations that haven't had
   native review. (The deployed host 404s on it until item 1.)

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
12. **Localize the app's own UI.** *(App)* Done, apart from native review.
    Labels, buttons, headings and validators go through `tr()`
    (`lib/i18n.dart`), looked up in `lib/ui_strings.dart`, generated from
    `ui-strings/ui_strings.json` (534 strings with hi / ta / te / mr, shared
    with web/). Every literal passed to `tr()` has an entry. Errors that carry
    a value (the server URL, an HTTP status) keep it in `args` and fill it in
    after translating (2026-10-03). Flutter's own text (the text-selection
    menu, tooltips) follows the app language through `flutter_localizations`,
    and iOS's `Info.plist` lists the five languages (not checked on iOS: no
    Mac). What's left:
    - **Native-speaker review.** Every hi / ta / te / mr string is
      author-written (`TODO: native_qa` in `ui-strings/gen_ui_strings.py`).
    - Text the server writes (answers, `/asr` notices, Supabase's own error
      messages) is in whatever language the server sends.
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

15. ~~**Hourly forecast** strip and chart.~~ ✅ Done (2026-10-03). `GET
    /forecast/hourly` serves the next 24 hours; Forecast → Hourly shows them as
    a strip under a temperature curve, "Now" first and each new day marked.
16. ~~**Structured 5–10 day list.**~~ ✅ Done (2026-10-03). `GET
    /forecast/daily?days=` serves up to 10 days; a live call now fetches all 10
    in one page. Forecast → Days lists them, and a tapped day shows its rain
    chance and millimetres, wind, humidity, UV, daylight, sunrise / sunset and
    night. Fixture mode has 5 days (the snapshots hold 5).
17. ~~**Sunrise / sunset / daylight progress.**~~ ✅ Done (2026-10-03). Each
    `/forecast/daily` day carries `sunrise` / `sunset`; Home's Daylight card
    shows the day length, both times and how much of the day has passed.
18. ~~**"Rain so far today" tile.**~~ ✅ Done (2026-10-03). `/facts` (current
    conditions) carries `rain_so_far` beside `facts`, so /ask's guardrail facts
    are unchanged; Home's card shows the millimetres since midnight with the IMD
    category, or the last 24 hours when the backend has no hourly history.
19. ~~**Emergency hotlines.**~~ ✅ Done (2026-10-03). `GET /hotlines` serves
    `data/hotlines.json`: 112, then each city's state, district and city lines.
    Every number was read off an official .gov.in / .nic.in page, kept with the
    page's wording, and checked on 2026-10-03; Chennai's 1913, NDMA's 1078 and
    Kerala's 1077 had only news sources and are left out. Re-check the list
    before a release. Alerts shows the numbers, tap to dial.

### P4 — engineering hygiene

20. ~~**CI job for mobile/.**~~ ✅ Done (2026-10-03): the `mobile` job in
    `.github/workflows/ci.yml` runs `flutter analyze`, `flutter test` and
    `flutter build apk --debug` on Flutter 3.47.2. It passed on GitHub
    Actions, first for 0bd9d8d.
21. **Better tests.** Widget tests run against flutter_test's stub HTTP (every
    call returns 400), so they cover error paths and layout only. `AskAnswer` is
    fixture-tested per branch; the History, cities and sign-in tests use a
    `MockClient`. The Windows-only temp-folder teardown failure in "the language
    is remembered across launches" is fixed (9fd163a: the test uses the
    in-memory store). Still needed:
    - Fixture-backed success-path tests for the remaining pages.
      `forecast_detail_test.dart` drives the whole app against a fake backend
      (`http.runWithClient`) for Home, Forecast and Alerts, plus an older
      backend's 404s and a 360 dp check in every language.
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
