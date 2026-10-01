// The app shell. Phones (the pics/ mockups): a sky-gradient top bar with the
// menu, the WeatherGPT mark and the bell, the page in the middle, and a
// five-tab bottom bar (Home, Chat, Forecast, Alerts, More = Settings). The
// drawer still carries web/'s Sidebar. Wide screens (tablets, desktop) keep
// web/'s permanent 256px sidebar instead of the bottom bar. Pages are built
// on first visit and kept alive after, so a chat transcript or an answer
// survives switching pages. All chrome colours come from the active
// persona's PersonaTheme.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../auth_client.dart';
import '../pages/aviation_page.dart';
import '../pages/best_window_page.dart';
import '../pages/profile_page.dart';
import '../persona_theme.dart';
import '../state/auth_store.dart';
import '../theme.dart';

enum AppPage { home, chat, forecast, alerts, settings }

class NavItem {
  final AppPage page;
  final String label;
  final IconData icon;
  final String shortLabel;
  final IconData activeIcon;
  const NavItem(this.page, this.label, this.icon, this.shortLabel, this.activeIcon);
}

/// Sidebar.tsx's NAV_ITEMS, minus History: GET /history only answers with a
/// Supabase bearer token, and this app has no sign-in flow to get one. The
/// short label and filled icon are the bottom bar's.
const List<NavItem> kNavItems = [
  NavItem(AppPage.home, 'Home', Icons.home_outlined, 'Home', Icons.home_rounded),
  NavItem(AppPage.chat, 'Chat & Evidence', Icons.chat_bubble_outline, 'Chat', Icons.chat_bubble),
  NavItem(AppPage.forecast, 'Forecast', Icons.light_mode_outlined, 'Forecast', Icons.light_mode),
  NavItem(AppPage.alerts, 'Alerts & Warnings', Icons.notifications_none, 'Alerts', Icons.notifications),
  NavItem(AppPage.settings, 'Settings', Icons.more_horiz, 'More', Icons.more_horiz),
];

/// Lets a page switch pages (e.g. Home's "See all" -> Forecast), or hand a
/// question to Chat ([ask]), which switches there and asks it.
class ShellNav extends InheritedWidget {
  final AppPage current;
  final ValueChanged<AppPage> go;

  /// The question [ask] handed over; Chat takes it and clears it.
  final ValueNotifier<String?> pendingAsk;

  const ShellNav({super.key, required this.current, required this.go, required this.pendingAsk, required super.child});

  static ShellNav of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<ShellNav>()!;

  static ShellNav read(BuildContext context) => context.getInheritedWidgetOfExactType<ShellNav>()!;

  void ask(String question) {
    pendingAsk.value = question;
    go(AppPage.chat);
  }

  @override
  bool updateShouldNotify(ShellNav oldWidget) => current != oldWidget.current;
}

class AppShell extends StatefulWidget {
  final Map<AppPage, WidgetBuilder> pages;
  const AppShell({super.key, required this.pages});

  /// Web Tailwind's `lg` is 1024px; below this the sidebar becomes a drawer.
  static const double wideBreakpoint = 1000;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  AppPage _current = AppPage.home;
  final Set<AppPage> _visited = {AppPage.home};
  final GlobalKey<ScaffoldState> _scaffold = GlobalKey<ScaffoldState>();
  final ValueNotifier<String?> _pendingAsk = ValueNotifier(null);

  @override
  void dispose() {
    _pendingAsk.dispose();
    super.dispose();
  }

  void _go(AppPage page) {
    if (page == _current) return;
    setState(() {
      _current = page;
      _visited.add(page);
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final stack = IndexedStack(
      index: _current.index,
      children: [
        for (final page in AppPage.values)
          // IndexedStack keeps hidden pages' tickers running; pause them.
          _visited.contains(page)
              ? TickerMode(enabled: page == _current, child: widget.pages[page]!(context))
              : const SizedBox.shrink(),
      ],
    );

    return ShellNav(
      current: _current,
      go: _go,
      pendingAsk: _pendingAsk,
      child: AnnotatedRegion<SystemUiOverlayStyle>(
        value: (t.isDark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark).copyWith(
          statusBarColor: Colors.transparent,
          systemNavigationBarColor: t.navBar,
          systemNavigationBarIconBrightness: t.isDark ? Brightness.light : Brightness.dark,
        ),
        // Android back returns to Home before it leaves the app.
        child: PopScope(
          canPop: _current == AppPage.home,
          onPopInvokedWithResult: (didPop, _) {
            if (didPop) return;
            // canPop: false also swallows the back press that would close an
            // open drawer, so close it here instead of changing page.
            final scaffold = _scaffold.currentState;
            if (scaffold != null && scaffold.isDrawerOpen) {
              scaffold.closeDrawer();
            } else {
              _go(AppPage.home);
            }
          },
          child: LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= AppShell.wideBreakpoint;
              final main = DecoratedBox(
                decoration: BoxDecoration(gradient: t.skyGradient),
                child: Column(
                  children: [
                    Topbar(showMenu: !wide),
                    Expanded(child: stack),
                  ],
                ),
              );
              return Scaffold(
                key: _scaffold,
                backgroundColor: t.skyBottom,
                drawer: wide
                    ? null
                    : Drawer(
                        child: Sidebar(
                          current: _current,
                          onSelect: (page) {
                            Navigator.of(context).pop();
                            _go(page);
                          },
                          onProfile: () {
                            Navigator.of(context).pop();
                            openProfile(context);
                          },
                          onAviation: () {
                            Navigator.of(context).pop();
                            openAviation(context);
                          },
                          onBestWindow: () {
                            Navigator.of(context).pop();
                            openBestWindow(context);
                          },
                        ),
                      ),
                bottomNavigationBar: wide ? null : BottomNav(current: _current, onSelect: _go),
                body: wide
                    ? Row(
                        children: [
                          Container(
                            width: 256,
                            decoration: BoxDecoration(color: t.surfaceContainerLowest, boxShadow: AppShadows.chrome),
                            child: Sidebar(
                              current: _current,
                              onSelect: _go,
                              onProfile: () => openProfile(context),
                              onAviation: () => openAviation(context),
                              onBestWindow: () => openBestWindow(context),
                            ),
                          ),
                          Expanded(child: main),
                        ],
                      )
                    : main,
              );
            },
          ),
        ),
      ),
    );
  }
}

/// The five-tab bar: filled accent icon + bold accent label on the active
/// tab (the pics/ mockups).
class BottomNav extends StatelessWidget {
  final AppPage current;
  final ValueChanged<AppPage> onSelect;
  const BottomNav({super.key, required this.current, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: t.navBar,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        boxShadow: [BoxShadow(color: t.shadow.withValues(alpha: 0.08), blurRadius: 16, offset: const Offset(0, -3))],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              for (final item in kNavItems)
                Expanded(
                  child: _BottomTab(item: item, active: item.page == current, onTap: () => onSelect(item.page)),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BottomTab extends StatelessWidget {
  final NavItem item;
  final bool active;
  final VoidCallback onTap;
  const _BottomTab({required this.item, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final fg = active ? t.primary : t.navIdle;
    return Semantics(
      selected: active,
      button: true,
      label: item.label,
      excludeSemantics: true,
      child: InkResponse(
        onTap: onTap,
        radius: 32,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(active ? item.activeIcon : item.icon, size: 25, color: fg),
            const SizedBox(height: 3),
            Text(
              item.shortLabel,
              style: AppText.bodySm.copyWith(
                fontSize: 11,
                height: 1.2,
                color: fg,
                fontWeight: active ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The WeatherGPT logo mark (assets/branding/: the light-theme and
/// dark-theme cuts of the logo, without the wordmark — the name is set as
/// text next to it).
class BrandMark extends StatelessWidget {
  final double size;
  const BrandMark({super.key, this.size = 30});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Image.asset(
      t.isDark ? 'assets/branding/weathergpt-mark-dark.png' : 'assets/branding/weathergpt-mark-light.png',
      width: size,
      height: size,
      filterQuality: FilterQuality.medium,
      excludeFromSemantics: true,
    );
  }
}

/// Sidebar.tsx: logo block + nav; the active item is a solid primary pill.
/// Below the pages: Profile, and the signed-in account's card at the foot
/// (both open the Profile page, which has Sign out).
class Sidebar extends StatelessWidget {
  final AppPage current;
  final ValueChanged<AppPage> onSelect;
  final VoidCallback? onProfile;

  /// Opens the Airport weather page (METAR / TAF), which isn't one of the
  /// five tabs — like Profile, a page pushed on top.
  final VoidCallback? onAviation;

  /// Opens the Best Time & What-if page — also pushed on top, like Profile
  /// and Airport weather.
  final VoidCallback? onBestWindow;
  const Sidebar({
    super.key,
    required this.current,
    required this.onSelect,
    this.onProfile,
    this.onAviation,
    this.onBestWindow,
  });

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final auth = AuthStore.maybeOf(context);
    final user = auth?.user;
    return SafeArea(
      right: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpace.lg),
            child: Row(
              children: [
                const BrandMark(size: 32),
                const SizedBox(width: AppSpace.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('WeatherGPT', style: AppText.headlineSm.copyWith(height: 1, letterSpacing: -0.45)),
                      const SizedBox(height: 2),
                      Text('Your AI weather assistant', style: AppText.bodySm.copyWith(color: t.onSurfaceVariant)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // Scrolls when the screen is too short for every tile (a phone held
          // sideways); the account card below stays pinned to the foot.
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: AppSpace.md),
              child: Column(
                children: [
                  for (final item in kNavItems)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: _NavTile(
                        icon: item.icon,
                        label: item.label,
                        active: item.page == current,
                        onTap: () => onSelect(item.page),
                      ),
                    ),
                  if (onAviation != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: _NavTile(
                        icon: Icons.flight_outlined,
                        label: 'Airport weather',
                        active: false,
                        onTap: onAviation!,
                      ),
                    ),
                  if (onBestWindow != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: _NavTile(
                        icon: Icons.schedule_outlined,
                        label: 'Best Time & What-if',
                        active: false,
                        onTap: onBestWindow!,
                      ),
                    ),
                  if (onProfile != null) ...[
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: AppSpace.sm),
                      child: Divider(color: t.outlineVariant.withValues(alpha: 0.6)),
                    ),
                    _NavTile(icon: Icons.account_circle_outlined, label: 'Profile', active: false, onTap: onProfile!),
                  ],
                ],
              ),
            ),
          ),
          if (onProfile != null && (user != null || auth?.isGuest == true)) _AccountCard(user: user, onTap: onProfile!),
        ],
      ),
    );
  }
}

/// The drawer's foot: avatar, name and email of the signed-in account, or
/// "Guest" with a nudge to sign in.
class _AccountCard extends StatelessWidget {
  final AuthUser? user;
  final VoidCallback onTap;
  const _AccountCard({required this.user, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final radius = BorderRadius.circular(AppRadius.card);
    return Padding(
      padding: const EdgeInsets.all(AppSpace.md),
      child: Material(
        color: t.tint,
        borderRadius: radius,
        child: InkWell(
          borderRadius: radius,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                if (user case final user?) ProfileAvatar(user: user, size: 40) else const GuestAvatar(size: 40),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user?.displayName ?? 'Guest',
                        overflow: TextOverflow.ellipsis,
                        style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                      ),
                      Text(
                        user?.email ?? 'Not signed in',
                        overflow: TextOverflow.ellipsis,
                        style: AppText.bodySm.copyWith(color: t.inkMuted),
                      ),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right, size: 20, color: t.inkMuted),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NavTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;
  const _NavTile({required this.icon, required this.label, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final fg = active ? t.onPrimary : t.onSurfaceVariant;
    return Semantics(
      selected: active,
      button: true,
      child: Material(
        color: active ? t.primary : Colors.transparent,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          hoverColor: t.surfaceContainerHigh,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 10),
            child: Row(
              children: [
                Icon(icon, size: 20, color: fg),
                const SizedBox(width: AppSpace.sm),
                Expanded(
                  child: Text(label, style: AppText.labelMd.copyWith(color: fg)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// The mockups' top bar: menu, the WeatherGPT mark and name, and the bell
/// (jumps to Alerts & Warnings). Transparent — it sits on the shell's sky.
/// The city pill lives just below it, in each page's scenery header.
class Topbar extends StatelessWidget {
  final bool showMenu;
  const Topbar({super.key, required this.showMenu});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return SafeArea(
      bottom: false,
      child: SizedBox(
        height: 56,
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: showMenu ? AppSpace.xs : AppSpace.lg),
          child: Row(
            children: [
              if (showMenu)
                IconButton(
                  tooltip: 'Menu',
                  icon: Icon(Icons.menu_rounded, color: t.ink),
                  onPressed: () => Scaffold.of(context).openDrawer(),
                ),
              const SizedBox(width: 2),
              const BrandMark(),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Text(
                  'WeatherGPT',
                  style: AppText.headlineSm.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
              ),
              IconButton(
                tooltip: 'Alerts & Warnings',
                icon: Icon(Icons.notifications_none_rounded, size: 24, color: t.ink),
                onPressed: () => ShellNav.read(context).go(AppPage.alerts),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
