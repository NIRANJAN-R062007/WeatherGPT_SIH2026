// A fake orchestrator for whole-app widget tests: every route the pages
// call, with replies shaped like services/orchestrator/main.py's and dates
// relative to now (so saved copies and "today" hold whenever a test runs).
// Run the app inside `http.runWithClient(..., () => backend.client)`.
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:weathergpt/auth_client.dart';
import 'package:weathergpt/state/auth_store.dart';

const _ist = Duration(hours: 5, minutes: 30);
const kFakeSource = 'Google Weather API (live)';

String _date(DateTime d) => d.toIso8601String().substring(0, 10);

/// Today's IST calendar date, at UTC midnight.
DateTime todayIst() {
  final ist = DateTime.now().toUtc().add(_ist);
  return DateTime.utc(ist.year, ist.month, ist.day);
}

/// GET /forecast/daily: ten days from today (IST).
Map<String, dynamic> dailyReply() => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'status': 'ok',
  'days': [
    for (var i = 0; i < 10; i++)
      {
        'label': ['today', 'tomorrow'].elementAtOrNull(i) ?? 'later',
        'date': _date(todayIst().add(Duration(days: i))),
        'condition': i == 2 ? 'thunderstorm_with_rain' : 'clear',
        'condition_label': i == 2 ? 'thunderstorm with rain' : 'clear',
        'night_condition': 'partly_cloudy',
        'night_condition_label': 'partly cloudy',
        'high_c': 32,
        'low_c': 27,
        'rain_probability_pct': i == 2 ? 70 : 15,
        'night_rain_probability_pct': 20,
        'rain_mm': i == 2 ? 12.4 : 0.07,
        'wind_kmh': 14,
        'humidity_pct': 68,
        'uv_index': 9,
        'sunrise': '${_date(todayIst().add(Duration(days: i)))}T00:28:00Z',
        'sunset': '${_date(todayIst().add(Duration(days: i)))}T12:27:00Z',
      },
  ],
  'provenance': {'source': kFakeSource, 'is_live': true, 'issued': '${_date(todayIst())}T01:30:00Z'},
};

/// GET /forecast/hourly: the 24 hours from the current one.
Map<String, dynamic> hourlyReply() {
  final now = DateTime.now().toUtc();
  final start = DateTime.utc(now.year, now.month, now.day, now.hour);
  return {
    'city': 'chennai',
    'city_name': 'Chennai',
    'status': 'ok',
    'hours': [
      for (var i = 0; i < 24; i++)
        {
          'time_iso': start.add(Duration(hours: i)).toIso8601String(),
          'local_time': '${start.add(Duration(hours: i)).add(_ist).hour.toString().padLeft(2, '0')}:00',
          'date': _date(start.add(Duration(hours: i)).add(_ist)),
          'temp_c': 26 + i % 7,
          'rain_probability_pct': i % 5 * 10,
          'condition': 'partly_cloudy',
          'condition_label': 'partly cloudy',
          'is_daytime': i < 10,
        },
    ],
    'provenance': {'source': kFakeSource, 'is_live': true, 'issued': start.toIso8601String()},
  };
}

/// GET /facts for one (intent, day).
Map<String, dynamic> factsReply(String intent, String day) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'condition_label': 'partly cloudy',
  'facts': {
    'condition': 'partly_cloudy',
    'temp_c': 31,
    'feels_like_c': 36,
    'humidity_pct': 70,
    'wind_kmh': 12,
    'rain_probability_pct': 25,
    'high_c': 32,
    'low_c': 27,
    'source': kFakeSource,
    'issued': DateTime.now().toUtc().toIso8601String(),
    'is_live': true,
  },
  if (intent == 'current_weather' && day == 'today')
    'rain_so_far': {
      'rain_so_far_mm': 0.56,
      'rain_category': 'light',
      'since': '${_date(todayIst())}T00:00:00+05:30',
      'source': kFakeSource,
      'is_live': true,
    },
};

const _legend = [
  {'colour': 'green', 'label': 'Green', 'meaning': 'No warning'},
  {'colour': 'yellow', 'label': 'Yellow', 'meaning': 'Be aware'},
  {'colour': 'orange', 'label': 'Orange', 'meaning': 'Be prepared'},
  {'colour': 'red', 'label': 'Red', 'meaning': 'Take action'},
];

/// GET /warnings with [status] 'active', 'clear' or 'unavailable'.
Map<String, dynamic> warningsReply(String status) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'status': status,
  'warning': status == 'unavailable'
      ? null
      : {
          'colour': status == 'active' ? 'orange' : 'green',
          'colour_label': status == 'active' ? 'Orange' : 'Green',
          'category_label': status == 'active' ? 'Heavy Rain' : '',
          'headline': status == 'active' ? 'Heavy rain likely at isolated places.' : 'No warnings in force',
          'advice': status == 'active' ? 'Avoid low-lying areas.' : '',
          'disclaimer': 'Simulated data — pending official feed access',
          'valid_from': '${_date(todayIst())}T00:00:00Z',
          'valid_to': '${_date(todayIst().add(const Duration(days: 1)))}T00:00:00Z',
          'issued_by': 'IMD Chennai',
          'source': 'fixture',
        },
  'legend': _legend,
};

/// GET /hotlines: the longest set (Hyderabad's, with GHMC's 11 digits).
const kHotlinesReply = {
  'city': 'hyderabad',
  'city_name': 'Hyderabad',
  'checked': '2026-10-03',
  'hotlines': [
    {'number': '112', 'dial': '112', 'name': 'Emergency', 'note': 'Any emergency, anywhere in India'},
    {
      'number': '1070',
      'dial': '1070',
      'name': 'State disaster helpline',
      'note': 'Floods, cyclones and other disasters',
    },
    {
      'number': '1077',
      'dial': '1077',
      'name': 'District disaster helpline',
      'note': "Your district's disaster control room",
    },
    {
      'number': '040 2111 1111',
      'dial': '04021111111',
      'name': 'GHMC helpline',
      'note': 'Greater Hyderabad Municipal Corporation',
    },
  ],
};

/// GET /ask: a grounded current-weather answer.
Map<String, dynamic> askReply() => {
  'intent': 'current_weather',
  'city': 'chennai',
  'day': 'today',
  'response': 'It is 31°C in Chennai with 70% humidity and a light breeze.',
  'provenance': {
    'source': kFakeSource,
    'issued': DateTime.now().toUtc().toIso8601String(),
    'is_live': true,
    'retrieved_at': DateTime.now().toUtc().toIso8601String(),
  },
  'grounding': {
    'ok': true,
    'matched': 2,
    'total': 2,
    'figures': [
      {'reading': '31°C', 'value': 31, 'unit': 'c', 'path': 'temp_c', 'matched': true},
      {'reading': '70%', 'value': 70, 'unit': '%', 'path': 'humidity_pct', 'matched': true},
    ],
    'fallback_used': false,
    'narration': 'llm',
    'attempts': 1,
    'provider': 'gemini',
  },
  'nlu': {
    'intent': 'current_weather',
    'city': 'Chennai',
    'time_window': 'now',
    'days': null,
    'parameter': 'all',
    'language': 'en',
    'source': 'rules',
    'confidence': 1.0,
  },
};

/// GET /aviation: Chennai airport with both reports.
Map<String, dynamic> aviationReply() => {
  'station': 'VOMM',
  'station_name': 'Chennai',
  'city': 'chennai',
  'status': 'ok',
  'metar': {
    'raw': 'METAR VOMM 292130Z 22005KT 4000 BR SCT020 SCT100 30/28 Q1010 NOSIG',
    'decoded': {
      'observed': {'day': 29, 'time_utc': '21:30', 'time_ist': '03:00'},
    },
    'lines': [
      'Chennai airport (VOMM), routine report observed at 03:00 IST (21:30 UTC on day 29 of the month).',
      'Wind from the southwest (220°) at 9 km/h (5 kt).',
      'Visibility 4 km.',
    ],
    'is_live': true,
    'retrieved_at': DateTime.now().toUtc().toIso8601String(),
    'source': 'aviationweather.gov',
  },
  'taf': {
    'raw': 'TAF VOMM 291700Z 2918/3024 25010KT 4000 -DZ/BR SCT018 TEMPO 2921/3003 SCT018',
    'decoded': {
      'issued': {'day': 29, 'time_utc': '17:00', 'time_ist': '22:30'},
    },
    'lines': [
      'Chennai airport (VOMM), terminal forecast (TAF) issued at 22:30 IST (17:00 UTC on day 29 of the month).',
      'Weather: light drizzle, mist.',
    ],
    'is_live': true,
    'retrieved_at': DateTime.now().toUtc().toIso8601String(),
    'source': 'aviationweather.gov',
  },
  'disclaimer':
      'For awareness only, not for flight planning. Use the official AAI / IMD aviation briefing before flying.',
};

/// GET /intelligence/best-window: a suitable window.
Map<String, dynamic> bestWindowReply(String day) => {
  'city': 'chennai',
  'city_name': 'Chennai',
  'day': day,
  'activity': 'outdoor',
  'status': 'ok',
  'window': {
    'start_local': '09:00',
    'end_local': '11:00',
    'avg_temp_c': 27.3,
    'max_rain_probability_pct': 15,
    'max_wind_kmh': 12,
    'hours': [],
  },
  'provenance': {'source': kFakeSource, 'is_live': true},
};

/// The backend while [online] says so; otherwise every request fails to
/// connect, as with no network.
class FakeBackend {
  bool online = true;
  String warningStatus = 'active';

  late final client = MockClient((req) async {
    if (!online) throw http.ClientException('Network is unreachable', req.url);
    final q = req.url.queryParameters;
    final Object? body = switch (req.url.path) {
      '/facts' => factsReply(q['intent'] ?? 'current_weather', q['day'] ?? 'today'),
      '/forecast/daily' => dailyReply(),
      '/forecast/hourly' => hourlyReply(),
      '/warnings' => warningsReply(warningStatus),
      '/hotlines' => kHotlinesReply,
      '/ask' => askReply(),
      '/aviation' => aviationReply(),
      '/intelligence/best-window' => bestWindowReply(q['day'] ?? 'today'),
      _ => null,
    };
    if (body == null) return http.Response('{"detail":"Not Found"}', 404);
    return http.Response(jsonEncode(body), 200, headers: {'content-type': 'application/json; charset=utf-8'});
  });
}

/// A guest session, with Supabase unreachable.
Future<AuthStore> guestAuth() async {
  final store = AuthStore(
    storage: MemorySessionStorage({'guest': true}),
    client: AuthClient(client: MockClient((_) async => http.Response('{}', 500))),
  );
  await store.restore();
  return store;
}
