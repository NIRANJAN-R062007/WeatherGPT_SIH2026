// Query history — opened from the drawer's "History" item: the signed-in
// user's past /ask questions with the answers shown for them, from GET
// /history (history_client.dart; web/src/pages/HistoryPage.tsx). Chat sends
// the user's token with every question, so signed-in questions are recorded
// server-side; a guest has no history and is invited to sign in. Filter chips
// group by intent, search matches the question, answer and city, "Ask again"
// re-asks in Chat, and "Clear history" erases everything (DELETE /history).
import 'package:flutter/material.dart';

import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../format.dart';
import '../history_client.dart';
import '../persona_theme.dart';
import '../state/auth_store.dart';
import '../theme.dart';
import 'auth_page.dart';
import '../i18n.dart';

/// [onAskAgain] hands a question to Chat (the shell's ShellNav.ask); the page
/// closes first. Without it the "Ask again" buttons are hidden.
Future<void> openHistory(BuildContext context, {ValueChanged<String>? onAskAgain}) {
  return Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => HistoryPage(onAskAgain: onAskAgain)));
}

const _filters = [(HistoryFilter.all, 'All queries'), (HistoryFilter.alerts, 'Alerts'), (HistoryFilter.rain, 'Rain')];

class HistoryPage extends StatelessWidget {
  /// Where the list comes from and how it is erased; tests pass stubs.
  final HistoryFetcher fetcher;
  final HistoryClearer clearer;
  final ValueChanged<String>? onAskAgain;

  const HistoryPage({super.key, this.fetcher = fetchHistory, this.clearer = clearHistory, this.onAskAgain});

  @override
  Widget build(BuildContext context) {
    final auth = AuthStore.of(context);
    if (auth.isGuest) return const _GuestHistory();
    // Signed out underneath us (the page is closing).
    if (auth.user == null) return const SubPageScaffold(body: SizedBox.shrink());
    final askAgain = onAskAgain == null
        ? null
        : (String question) {
            Navigator.of(context).popUntil((r) => r.isFirst);
            onAskAgain!(question);
          };
    return _SignedInHistory(fetcher: fetcher, clearer: clearer, onAskAgain: askAgain);
  }
}

/// A guest's History: what an account adds, and the ways to get one.
class _GuestHistory extends StatelessWidget {
  const _GuestHistory();

  @override
  Widget build(BuildContext context) {
    void open(AuthMode mode) =>
        Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => AuthPage(initialMode: mode)));
    return SubPageScaffold(
      body: PageFrame(
        showCityPill: false,
        children: [
          const PageHeader(
            title: 'Query history',
            subtitle: 'Past weather questions and the answers returned for them.',
          ),
          const SizedBox(height: AppSpace.lg),
          for (final (icon, text) in const [
            (Icons.history, 'Your questions are saved to your account'),
            (Icons.devices_outlined, 'The same history on any device you sign in on'),
          ])
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpace.sm),
              child: ActionRow(icon: icon, title: text, trailing: const SizedBox.shrink()),
            ),
          const SizedBox(height: AppSpace.lg),
          GradientButton(label: 'Sign in to see your history', onPressed: () => open(AuthMode.signIn)),
          const SizedBox(height: 12),
          OutlineActionButton(label: 'Create account', onPressed: () => open(AuthMode.signUp)),
        ],
      ),
    );
  }
}

class _SignedInHistory extends StatefulWidget {
  final HistoryFetcher fetcher;
  final HistoryClearer clearer;
  final ValueChanged<String>? onAskAgain;
  const _SignedInHistory({required this.fetcher, required this.clearer, required this.onAskAgain});

  @override
  State<_SignedInHistory> createState() => _SignedInHistoryState();
}

class _SignedInHistoryState extends State<_SignedInHistory> {
  List<HistoryRow>? _rows;
  HistoryError? _error;
  HistoryFilter _filter = HistoryFilter.all;
  final TextEditingController _search = TextEditingController();
  bool _clearing = false;
  String? _clearError;
  int _requestId = 0;

  @override
  void initState() {
    super.initState();
    _search.addListener(() => setState(() {}));
    _fetch();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _reload() {
    setState(() {
      _rows = null;
      _error = null;
    });
    return _fetch();
  }

  Future<void> _fetch() async {
    final id = ++_requestId;
    final auth = AuthStore.read(context);
    try {
      final token = await auth.accessToken();
      if (token == null) {
        throw HistoryError(HistoryErrorKind.auth, 'Your session has expired. Sign in again to see your history.');
      }
      final rows = await widget.fetcher(token);
      if (!mounted || id != _requestId) return;
      setState(() => _rows = rows);
    } catch (e) {
      if (!mounted || id != _requestId) return;
      setState(
        () => _error = e is HistoryError
            ? e
            : HistoryError(HistoryErrorKind.network, 'Something went wrong loading your history.'),
      );
    }
  }

  Future<void> _confirmClear() async {
    final t = PersonaTheme.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(tr(context, 'Clear your history?'), style: AppText.headlineSm.copyWith(color: t.ink)),
        content: Text(
          tr(context, "This permanently erases every saved question and answer from your account. It can't be undone."),
          style: AppText.bodyMd.copyWith(color: t.inkMuted),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(tr(context, 'Cancel'))),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(tr(context, 'Clear history')),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await _clear();
  }

  Future<void> _clear() async {
    final auth = AuthStore.read(context);
    setState(() {
      _clearing = true;
      _clearError = null;
    });
    final lang = langOf(context);
    String? error;
    try {
      final token = await auth.accessToken();
      if (token == null) {
        throw HistoryError(HistoryErrorKind.auth, 'Your session has expired. Sign in again to clear your history.');
      }
      await widget.clearer(token);
    } catch (e) {
      error = e is HistoryError ? trIn(lang, e.message, e.args) : 'Something went wrong clearing your history.';
    }
    if (!mounted) return;
    setState(() {
      _clearing = false;
      _clearError = error;
      if (error == null) _rows = [];
    });
  }

  void _signOutAndIn() {
    final auth = AuthStore.read(context);
    Navigator.of(context).popUntil((r) => r.isFirst);
    auth.signOut();
  }

  @override
  Widget build(BuildContext context) {
    final rows = _rows;
    final error = _error;
    return SubPageScaffold(
      body: PageFrame(
        showCityPill: false,
        onRefresh: _reload,
        children: [
          const PageHeader(
            title: 'Query history',
            subtitle: 'Past weather questions and the answers returned for them.',
          ),
          const SizedBox(height: AppSpace.lg),
          if (error != null) ...[
            ErrorPanel(
              icon: error.kind == HistoryErrorKind.auth ? Icons.lock_outline : Icons.cloud_off,
              title: error.kind == HistoryErrorKind.auth ? 'Sign in again' : 'History unavailable',
              message: error.message,
              messageArgs: error.args,
              onRetry: error.kind == HistoryErrorKind.auth ? null : _reload,
            ),
            if (error.kind == HistoryErrorKind.auth) ...[
              const SizedBox(height: AppSpace.sm),
              OutlineActionButton(
                label: 'Sign out and sign in again',
                icon: Icons.logout_rounded,
                onPressed: _signOutAndIn,
              ),
            ],
          ] else if (rows == null)
            const LoadingPanel('Loading your history…')
          else if (rows.isEmpty)
            ActionRow(
              leading: const IconDisc(Icons.chat_bubble_outline, solid: true),
              title: 'No questions yet',
              subtitle: 'Ask something in Chat and it will show up here.',
              onTap: widget.onAskAgain == null
                  ? null
                  : () => widget.onAskAgain!(tr(context, 'What is the weather like today?')),
              trailing: widget.onAskAgain == null ? const SizedBox.shrink() : null,
            )
          else
            ..._list(context, rows),
        ],
      ),
    );
  }

  List<Widget> _list(BuildContext context, List<HistoryRow> rows) {
    final t = PersonaTheme.of(context);
    final q = _search.text.trim().toLowerCase();
    // The city is searchable by its English name and its name in the app language.
    String haystack(HistoryRow r) =>
        '${r.query} ${r.response ?? ''} ${cityLabel(r.city)} ${tr(context, cityLabel(r.city))}'.toLowerCase();
    final shown = [
      for (final r in rows)
        if (matchesFilter(r, _filter) && (q.isEmpty || haystack(r).contains(q))) r,
    ];
    return [
      _FilterChips(value: _filter, onChanged: (f) => setState(() => _filter = f)),
      const SizedBox(height: AppSpace.sm),
      AppTextField(
        controller: _search,
        label: 'Search history',
        hint: 'Search questions, answers, cities',
        icon: Icons.search,
        textInputAction: TextInputAction.search,
      ),
      const SizedBox(height: AppSpace.md),
      SectionTitle(tr(context, shown.length == 1 ? '{n} question' : '{n} questions', {'n': shown.length})),
      const SizedBox(height: AppSpace.sm),
      if (shown.isEmpty)
        Text(tr(context, 'Nothing matches that filter.'), style: AppText.bodyMd.copyWith(color: t.inkMuted))
      else
        for (final r in shown) ...[
          _HistoryCard(row: r, onAskAgain: widget.onAskAgain),
          const SizedBox(height: AppSpace.md),
        ],
      const SizedBox(height: AppSpace.lg),
      OutlineActionButton(
        label: _clearing ? 'Clearing…' : 'Clear history',
        icon: Icons.delete_sweep_outlined,
        destructive: true,
        onPressed: _clearing ? null : _confirmClear,
      ),
      if (_clearError != null) ...[
        const SizedBox(height: AppSpace.sm),
        Text(tr(context, _clearError!), style: AppText.bodyMd.copyWith(color: AppColors.error)),
      ],
    ];
  }
}

/// "All queries / Alerts / Rain": the selected pill takes the accent.
class _FilterChips extends StatelessWidget {
  final HistoryFilter value;
  final ValueChanged<HistoryFilter> onChanged;
  const _FilterChips({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final (filter, label) in _filters)
          Semantics(
            selected: filter == value,
            button: true,
            child: Material(
              color: filter == value ? t.primary : t.tint,
              borderRadius: BorderRadius.circular(999),
              child: InkWell(
                borderRadius: BorderRadius.circular(999),
                onTap: () => onChanged(filter),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  child: Text(
                    tr(context, label),
                    style: AppText.labelMd.copyWith(
                      color: filter == value ? t.onPrimary : t.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// One past question: city / intent / language chips and the time, the
/// question, the answer that was shown, and "Ask again".
class _HistoryCard extends StatelessWidget {
  final HistoryRow row;
  final ValueChanged<String>? onAskAgain;
  const _HistoryCard({required this.row, required this.onAskAgain});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final when = row.createdAt.isEmpty
        ? ''
        : '${istDayMonth(row.createdAt, lang: langOf(context))}, ${istTime(row.createdAt)}';
    return AppCard(
      padding: const EdgeInsets.all(AppSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    if (row.city case final city?) TagChip(cityLabel(city), icon: Icons.location_on_outlined),
                    if (row.intent case final intent?)
                      TagChip(intent.replaceAll('_', ' ').toUpperCase(), tone: ChipTone.primary),
                    if (row.lang case final lang? when lang != 'en') TagChip(lang.toUpperCase()),
                  ],
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Text(when, style: AppText.citationMono.copyWith(color: t.outline)),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text('“${row.query}”', style: AppText.headlineSm.copyWith(color: t.ink, height: 1.3)),
          const SizedBox(height: AppSpace.sm),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpace.md),
            decoration: BoxDecoration(color: t.tint, borderRadius: BorderRadius.circular(AppRadius.xl)),
            child: Text(
              row.response ?? tr(context, 'No answer was recorded for this question.'),
              style: AppText.bodyMd.copyWith(color: row.response == null ? t.inkMuted : t.ink),
            ),
          ),
          if (onAskAgain != null) ...[
            const SizedBox(height: AppSpace.md),
            PillButton(icon: Icons.refresh, label: 'Ask again', onPressed: () => onAskAgain!(row.query)),
          ],
        ],
      ),
    );
  }
}
