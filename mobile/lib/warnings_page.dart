// Warning colour-code rendering (mobile) — plan.md §8 Phase 3, Chelsea's
// item. GET /warnings?city=&lang= gives a flatter shape than /ask's warnings
// branch: city, city_name, status, warning, legend (services/orchestrator/
// main.py's warnings_route(), imd_warnings.public()).
import 'package:flutter/material.dart';

import 'cities.dart';
import 'config.dart';
import 'warning_colors.dart';
import 'warnings_client.dart';

class WarningsPage extends StatefulWidget {
  const WarningsPage({super.key});

  @override
  State<WarningsPage> createState() => _WarningsPageState();
}

class _WarningsPageState extends State<WarningsPage> {
  City _city = kCities.first;
  String _lang = 'en';
  Map<String, dynamic>? _result;
  Object? _error;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await fetchWarnings(city: _city.key, lang: _lang);
      setState(() => _result = result);
    } catch (e) {
      setState(() => _error = e);
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: _city.key,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'City', isDense: true),
                  items: kCities
                      .map((c) => DropdownMenuItem(
                            value: c.key,
                            child: Text(c.name, overflow: TextOverflow.ellipsis),
                          ))
                      .toList(),
                  onChanged: (v) {
                    if (v == null) return;
                    setState(() => _city = cityByKey(v));
                    _load();
                  },
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: _lang,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Language', isDense: true),
                  items: kSupportedLanguages
                      .map((l) => DropdownMenuItem(
                            value: l,
                            child: Text(kLanguageLabels[l] ?? l, overflow: TextOverflow.ellipsis),
                          ))
                      .toList(),
                  onChanged: (v) {
                    if (v == null) return;
                    setState(() => _lang = v);
                    _load();
                  },
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (_loading) const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator())),
          if (!_loading && _error != null) _errorCard('$_error'),
          if (!_loading && _error == null && _result != null) _resultCard(_result!),
          if (!_loading && _error == null && _result != null) _legendCard(_result!),
        ],
      ),
    );
  }

  Widget _errorCard(String message) {
    return Card(
      color: const Color(0xFFFDECEA),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(message),
      ),
    );
  }

  Widget _resultCard(Map<String, dynamic> result) {
    final status = result['status'] as String? ?? 'unavailable';
    final warning = result['warning'] as Map<String, dynamic>?;

    // plan.md §2 principle 3: `unavailable` is a "no verdict" — the feed is
    // off, or the fixture is missing/malformed. It must never render as a
    // green all-clear, so it gets its own neutral card, no colour band.
    if (status == 'unavailable' || warning == null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: const [
              Icon(Icons.info_outline, color: Colors.black54),
              SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Warnings not available for this city right now.',
                  style: TextStyle(fontStyle: FontStyle.italic, color: Colors.black54),
                ),
              ),
            ],
          ),
        ),
      );
    }

    final colour = warning['colour'] as String?;
    final accent = warningColor(colour);
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: accent, width: 2),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 14,
                  height: 14,
                  decoration: BoxDecoration(color: accent, shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Text(
                  (warning['colour_label'] as String?) ?? colour ?? '',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: accent),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(warning['headline'] as String? ?? '', style: const TextStyle(fontSize: 15)),
            if (warning['category_label'] != null) ...[
              const SizedBox(height: 4),
              Text(warning['category_label'] as String, style: const TextStyle(fontSize: 13)),
            ],
            if (warning['advice'] != null) ...[
              const SizedBox(height: 8),
              Text(
                warning['advice'] as String,
                style: const TextStyle(fontSize: 13, color: Colors.black87),
              ),
            ],
            const SizedBox(height: 8),
            Text(
              'Valid ${warning['valid_from']} to ${warning['valid_to']} · ${warning['issued_by']}',
              style: const TextStyle(fontSize: 11, color: Colors.black54),
            ),
          ],
        ),
      ),
    );
  }

  Widget _legendCard(Map<String, dynamic> result) {
    final legend = (result['legend'] as List<dynamic>?) ?? const [];
    if (legend.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Colour-code legend', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              for (final row in legend.cast<Map<String, dynamic>>())
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        margin: const EdgeInsets.only(top: 3),
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: warningColor(row['colour'] as String?),
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(row['label'] as String? ?? '',
                                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                            Text(row['meaning'] as String? ?? '',
                                style: const TextStyle(fontSize: 12, color: Colors.black54)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
