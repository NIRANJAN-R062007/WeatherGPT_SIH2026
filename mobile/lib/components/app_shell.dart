// The app shell — web/src/components/Layout.tsx + Sidebar.tsx + Topbar.tsx.
// Wide screens (tablets, desktop) get the same permanent 256px sidebar as
// web/; phones get it as a drawer behind the Topbar's menu button. Pages are
// built on first visit and kept alive after, so a chat transcript or an
// answer survives switching pages.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../state/ui_prefs.dart';
import '../theme.dart';
import 'common.dart';

enum AppPage { home, chat, forecast, alerts, settings }

class NavItem {
  final AppPage page;
  final String label;
  final IconData icon;
  const NavItem(this.page, this.label, this.icon);
}

/// Sidebar.tsx's NAV_ITEMS, minus History: GET /history only answers with a
/// Supabase bearer token, and this app has no sign-in flow to get one.
const List<NavItem> kNavItems = [
  NavItem(AppPage.home, 'Home', Icons.grid_view),
  NavItem(AppPage.chat, 'Chat & Evidence', Icons.forum_outlined),
  NavItem(AppPage.forecast, 'Forecast', Icons.wb_cloudy_outlined),
  NavItem(AppPage.alerts, 'Alerts & Warnings', Icons.crisis_alert),
  NavItem(AppPage.settings, 'Settings', Icons.tune),
];

/// Lets a page switch pages (e.g. Home's Voice Assistant tile -> Chat).
class ShellNav extends InheritedWidget {
  final AppPage current;
  final ValueChanged<AppPage> go;
  const ShellNav({super.key, required this.current, required this.go, required super.child});

  static ShellNav of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<ShellNav>()!;

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

  void _go(AppPage page) {
    if (page == _current) return;
    setState(() {
      _current = page;
      _visited.add(page);
    });
  }

  @override
  Widget build(BuildContext context) {
    final stack = IndexedStack(
      index: _current.index,
      children: [
        for (final page in AppPage.values)
          // IndexedStack keeps hidden pages' tickers running; pause them so
          // Home's ambient gradient doesn't animate behind other pages.
          _visited.contains(page)
              ? TickerMode(enabled: page == _current, child: widget.pages[page]!(context))
              : const SizedBox.shrink(),
      ],
    );

    return ShellNav(
      current: _current,
      go: _go,
      child: AnnotatedRegion<SystemUiOverlayStyle>(
        value: SystemUiOverlayStyle.dark.copyWith(statusBarColor: Colors.transparent),
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
              return Scaffold(
                key: _scaffold,
                backgroundColor: AppColors.surface,
                drawer: wide
                    ? null
                    : Drawer(
                        child: Sidebar(
                          current: _current,
                          onSelect: (page) {
                            Navigator.of(context).pop();
                            _go(page);
                          },
                        ),
                      ),
                body: wide
                    ? Row(
                        children: [
                          Container(
                            width: 256,
                            decoration: const BoxDecoration(
                              color: AppColors.surfaceContainerLowest,
                              boxShadow: AppShadows.chrome,
                            ),
                            child: Sidebar(current: _current, onSelect: _go),
                          ),
                          Expanded(
                            child: Column(
                              children: [
                                const Topbar(showMenu: false),
                                Expanded(child: stack),
                              ],
                            ),
                          ),
                        ],
                      )
                    : Column(
                        children: [
                          const Topbar(showMenu: true),
                          Expanded(child: stack),
                        ],
                      ),
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Sidebar.tsx: logo block + nav; the active item is a solid primary pill.
class Sidebar extends StatelessWidget {
  final AppPage current;
  final ValueChanged<AppPage> onSelect;
  const Sidebar({super.key, required this.current, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      right: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpace.lg),
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(AppRadius.md),
                  ),
                  child: const Icon(Icons.cloud_outlined, size: 20, color: AppColors.onPrimary),
                ),
                const SizedBox(width: AppSpace.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('WeatherGPT', style: AppText.headlineSm.copyWith(height: 1, letterSpacing: -0.45)),
                      const SizedBox(height: 2),
                      Text(
                        'Your AI weather assistant',
                        style: AppText.bodySm.copyWith(color: AppColors.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpace.md),
            child: Column(
              children: [
                for (final item in kNavItems)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: _NavTile(item: item, active: item.page == current, onTap: () => onSelect(item.page)),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _NavTile extends StatelessWidget {
  final NavItem item;
  final bool active;
  final VoidCallback onTap;
  const _NavTile({required this.item, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final fg = active ? AppColors.onPrimary : AppColors.onSurfaceVariant;
    return Semantics(
      selected: active,
      button: true,
      child: Material(
        color: active ? AppColors.primary : Colors.transparent,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          hoverColor: AppColors.surfaceContainerHigh,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 10),
            child: Row(
              children: [
                Icon(item.icon, size: 20, color: fg),
                const SizedBox(width: AppSpace.sm),
                Expanded(
                  child: Text(item.label, style: AppText.labelMd.copyWith(color: fg)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Topbar.tsx: the city pill (shared city for every page's calls) and the
/// bell, which here jumps to Alerts & Warnings.
class Topbar extends StatelessWidget {
  final bool showMenu;
  const Topbar({super.key, required this.showMenu});

  @override
  Widget build(BuildContext context) {
    final prefs = UiPrefs.of(context);
    final city = prefs.cityInfo;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surfaceContainerLowest.withValues(alpha: 0.9),
        boxShadow: AppShadows.chrome,
      ),
      child: SafeArea(
        bottom: false,
        child: SizedBox(
          height: 64,
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: showMenu ? AppSpace.sm : AppSpace.xl),
            child: Row(
              children: [
                if (showMenu)
                  IconButton(
                    tooltip: 'Menu',
                    icon: const Icon(Icons.menu, color: AppColors.onSurfaceVariant),
                    onPressed: () => Scaffold.of(context).openDrawer(),
                  ),
                Expanded(
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Material(
                      color: AppColors.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(999),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(999),
                        onTap: () => showCityPicker(context),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.location_on_outlined, size: 18, color: AppColors.primary),
                              const SizedBox(width: 6),
                              Flexible(
                                child: Text(
                                  '${city.name}, ${city.region}',
                                  overflow: TextOverflow.ellipsis,
                                  style: AppText.labelMd.copyWith(color: AppColors.onSurface),
                                ),
                              ),
                              const SizedBox(width: 4),
                              const Icon(Icons.expand_more, size: 16, color: AppColors.onSurfaceVariant),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                IconButton(
                  tooltip: 'Alerts & Warnings',
                  icon: const Icon(Icons.notifications_outlined, size: 22, color: AppColors.onSurfaceVariant),
                  onPressed: () => ShellNav.of(context).go(AppPage.alerts),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
