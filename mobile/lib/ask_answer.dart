// Branch-aware renderer for one /ask reply. Mirrors
// web/src/components/AskAnswer.tsx's branch handling so the mobile and web
// clients show the same thing for the same backend response.
import 'package:flutter/material.dart';

import 'api_client.dart';
import 'warning_colors.dart';

class AskAnswerCard extends StatelessWidget {
  final AskOutcome outcome;
  const AskAnswerCard({super.key, required this.outcome});

  @override
  Widget build(BuildContext context) {
    switch (outcome.kind) {
      case AskKind.success:
        return _successCard(context);
      case AskKind.warnings:
        return _warningsCard(context);
      case AskKind.warningsUnavailable:
        return _warningsUnavailableCard(context);
      case AskKind.ungrounded:
        return _ungroundedCard(context);
      case AskKind.fallback:
        return _fallbackCard(context);
    }
  }

  Widget _bubble({required Widget child, Color? accent}) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF4F6F8),
        borderRadius: BorderRadius.circular(12),
        border: accent != null ? Border(left: BorderSide(color: accent, width: 4)) : null,
      ),
      child: child,
    );
  }

  Widget _provenanceLine(Map<String, dynamic>? provenance) {
    if (provenance == null) return const SizedBox.shrink();
    final source = provenance['source'] as String? ?? '';
    final issued = provenance['issued'] as String? ?? provenance['issued_by'] as String?;
    final retrieved = provenance['retrieved_at'] as String?;
    final parts = <String>[
      if (source.isNotEmpty) source,
      if (issued != null) 'issued $issued',
      if (retrieved != null) 'retrieved $retrieved',
    ];
    if (parts.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Text(
        parts.join(' · '),
        style: const TextStyle(fontSize: 11, color: Colors.black54),
      ),
    );
  }

  Widget _noticeLine(String? notice) {
    if (notice == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Text(notice, style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
    );
  }

  Widget _successCard(BuildContext context) {
    final data = outcome.data;
    return _bubble(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(data['response'] as String? ?? '', style: const TextStyle(fontSize: 15)),
          _provenanceLine(data['provenance'] as Map<String, dynamic>?),
          _noticeLine(data['notice'] as String?),
        ],
      ),
    );
  }

  Widget _warningsCard(BuildContext context) {
    final data = outcome.data;
    final warning = data['warning'] as Map<String, dynamic>?;
    final colour = warning?['colour'] as String?;
    return _bubble(
      accent: warningColor(colour),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(color: warningColor(colour), shape: BoxShape.circle),
              ),
              const SizedBox(width: 6),
              Text(
                (warning?['colour_label'] as String?) ?? colour ?? '',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(data['response'] as String? ?? '', style: const TextStyle(fontSize: 15)),
          if (warning?['category_label'] != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(warning!['category_label'] as String, style: const TextStyle(fontSize: 13)),
            ),
          _provenanceLine(data['provenance'] as Map<String, dynamic>?),
          _noticeLine(data['notice'] as String?),
        ],
      ),
    );
  }

  Widget _warningsUnavailableCard(BuildContext context) {
    final data = outcome.data;
    // plan.md §2 principle 3: unavailable is a "no verdict", never rendered
    // as a green all-clear.
    return _bubble(
      accent: Colors.grey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            data['message'] as String? ?? 'Warnings not available.',
            style: const TextStyle(fontSize: 15, fontStyle: FontStyle.italic, color: Colors.black54),
          ),
          _noticeLine(data['notice'] as String?),
        ],
      ),
    );
  }

  Widget _ungroundedCard(BuildContext context) {
    final data = outcome.data;
    return _bubble(
      accent: Colors.orange,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(data['message'] as String? ?? '', style: const TextStyle(fontSize: 15)),
          _provenanceLine(data['provenance'] as Map<String, dynamic>?),
          _noticeLine(data['notice'] as String?),
        ],
      ),
    );
  }

  Widget _fallbackCard(BuildContext context) {
    final data = outcome.data;
    return _bubble(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(data['message'] as String? ?? '', style: const TextStyle(fontSize: 15)),
          _noticeLine(data['notice'] as String?),
        ],
      ),
    );
  }
}
