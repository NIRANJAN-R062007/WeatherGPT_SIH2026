// Alerts & Warnings — web/src/pages/AlertsPage.tsx's live card: GET
// /warnings for the selected city, rendered as loading / error / "no
// verdict" (never green) / the colour verdict with its legend. The web
// page's category tiles, advisory detail, geofence explainer, hotlines and
// adjacent-sectors panels are static samples with no endpoint behind them
// and are not carried over.
import 'package:flutter/material.dart';

import '../components/ask_answer.dart';
import '../components/common.dart';
import '../format.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import '../warning_colors.dart';
import '../warnings_client.dart';

class AlertsPage extends StatefulWidget {
  const AlertsPage({super.key});

  @override
  State<AlertsPage> createState() => _AlertsPageState();
}

class _AlertsPageState extends State<AlertsPage> {
  String? _city;
  String? _lang;
  bool _loading = false;
  Map<String, dynamic>? _data;
  WarningsError? _error;
  int _requestId = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Fetch on first build and whenever the shared city or language changes.
    // A build always follows, so no setState here.
    final prefs = UiPrefs.of(context);
    if (prefs.city != _city || prefs.lang != _lang) _load(prefs.city, prefs.lang);
  }

  /// Synchronous part is plain assignment — callers outside a build wrap
  /// the call in setState.
  Future<void> _load(String city, String lang) {
    if (city != _city) _data = null;
    _city = city;
    _lang = lang;
    _loading = true;
    _error = null;
    return _fetch(++_requestId, city, lang);
  }

  Future<void> _fetch(int id, String city, String lang) async {
    try {
      final data = await fetchWarnings(city: city, lang: lang);
      if (!mounted || id != _requestId) return;
      setState(() {
        _data = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || id != _requestId) return;
      setState(() {
        _error = e is WarningsError
            ? e
            : WarningsError(WarningsErrorKind.network, 'Something went wrong talking to the warnings service.');
        _data = null;
        _loading = false;
      });
    }
  }

  Future<void> _reload() {
    final prefs = UiPrefs.read(context);
    late Future<void> done;
    setState(() => done = _load(prefs.city, prefs.lang));
    return done;
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    return RefreshIndicator(
      onRefresh: _reload,
      child: ListView(
        padding: const EdgeInsets.all(AppSpace.gutter),
        children: [
          const PageHeader(
            title: 'Alerts & Warnings',
            subtitle: 'IMD colour-coded warnings for your city, shown exactly as the feed issues them.',
          ),
          const SizedBox(height: AppSpace.lg),
          SurfaceCard(
            radius: AppRadius.xl,
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const RuleLabel(icon: Icons.bolt, text: 'Live — data from /warnings'),
              const SizedBox(height: AppSpace.sm),
              const CityHintRow(prefix: 'City', icon: Icons.location_on_outlined, showLang: false),
              const SizedBox(height: AppSpace.sm),
              if (_loading)
                const LoadingPanel('Checking current warnings…')
              else if (_error != null)
                ErrorPanel(
                  icon: Icons.wifi_off,
                  title: 'Warnings service unreachable',
                  message: _error!.message,
                  onRetry: _reload,
                )
              else if (data != null && data['warning'] is Map<String, dynamic>)
                _Verdict(data)
              else if (data != null)
                _NoVerdict(data),
            ]),
          ),
          const SizedBox(height: AppSpace.lg),
          const _SourceNote(),
        ],
      ),
    );
  }
}

/// `status` "unavailable" (or an older backend's bare `warning: null`):
/// deliberately neutral, never green — no verdict is not an all-clear.
class _NoVerdict extends StatelessWidget {
  final Map<String, dynamic> data;
  const _NoVerdict(this.data);

  @override
  Widget build(BuildContext context) {
    final cityName = data['city_name'] as String? ?? cityLabel(data['city'] as String?);
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColors.surfaceContainer,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.help_outline, size: 18, color: AppColors.onSurfaceVariant),
            const SizedBox(width: 4),
            Text(
              'No warning verdict',
              style: AppText.labelMd.copyWith(color: AppColors.onSurfaceVariant, fontWeight: FontWeight.w700),
            ),
          ]),
          TagChip(cityName, icon: Icons.location_on_outlined),
        ]),
        const SizedBox(height: AppSpace.sm),
        Text(
          "Weather warnings aren't available right now for $cityName — this can't be read as an all-clear.",
          style: AppText.bodyMd.copyWith(color: AppColors.onSurface),
        ),
        const SizedBox(height: AppSpace.sm),
        WarningLegend(rows: data['legend']),
      ]),
    );
  }
}

/// AlertsPage.tsx's LiveVerdict.
class _Verdict extends StatelessWidget {
  final Map<String, dynamic> data;
  const _Verdict(this.data);

  @override
  Widget build(BuildContext context) {
    final w = data['warning'] as Map<String, dynamic>;
    final colour = w['colour'] as String?;
    final active = (data['status'] ?? (colour == 'green' ? 'clear' : 'active')) == 'active';
    final colourText = warningColor(colour);
    String s(String k) => w[k] is String ? w[k] as String : '';

    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        WarningBand(colour),
        const SizedBox(height: AppSpace.sm),
        Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(active ? Icons.warning_amber : Icons.check_circle_outline, size: 18, color: colourText),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                '${s('colour_label')}${active ? ' — in force' : ' — nothing in force'}',
                style: AppText.labelMd.copyWith(color: colourText, fontWeight: FontWeight.w700),
              ),
            ),
          ]),
          TagChip(
            data['city_name'] as String? ?? cityLabel(data['city'] as String?),
            icon: Icons.location_on_outlined,
          ),
          if (s('category_label').isNotEmpty) TagChip(s('category_label'), tone: ChipTone.primary),
        ]),
        const SizedBox(height: AppSpace.sm),
        Text(s('headline'), style: AppText.bodyLg.copyWith(color: AppColors.onSurface)),
        if (s('advice').isNotEmpty) ...[
          const SizedBox(height: AppSpace.sm),
          Text(s('advice'), style: AppText.bodyMd.copyWith(color: AppColors.onSurfaceVariant)),
        ],
        const SizedBox(height: AppSpace.sm),
        WarningLegend(rows: data['legend'], highlight: colour),
        const SizedBox(height: AppSpace.xs),
        Container(
          padding: const EdgeInsets.only(top: AppSpace.xs),
          decoration: BoxDecoration(
            border: Border(top: BorderSide(color: AppColors.outlineVariant.withValues(alpha: 0.4))),
          ),
          child: DefaultTextStyle.merge(
            style: AppText.citationMono.copyWith(color: AppColors.onSurfaceVariant),
            child: Wrap(spacing: 12, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
              Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.campaign_outlined, size: 12, color: AppColors.onSurfaceVariant),
                const SizedBox(width: 4),
                Flexible(child: Text(s('issued_by'))),
              ]),
              Text('Valid ${istTimestamp(s('valid_from'))} → ${istTimestamp(s('valid_to'))}'),
              Text('source: ${s('source')}', style: const TextStyle(color: AppColors.outline)),
            ]),
          ),
        ),
      ]),
    );
  }
}

/// AlertsPage.tsx's source note, reworded to what the backend actually does.
class _SourceNote extends StatelessWidget {
  const _SourceNote();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppRadius.xl),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.verified_outlined, size: 18, color: AppColors.primary),
          const SizedBox(width: AppSpace.sm),
          Text('Source', style: AppText.labelMd.copyWith(fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: AppSpace.sm),
        Text(
          'The colour code and headline are the warning feed\'s own, shown verbatim — WeatherGPT '
          'explains a colour, it never re-grades one. The source line on each verdict names the feed '
          'that answered.',
          style: AppText.bodySm.copyWith(color: AppColors.onSurfaceVariant),
        ),
      ]),
    );
  }
}
