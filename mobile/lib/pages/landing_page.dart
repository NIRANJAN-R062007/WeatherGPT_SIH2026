// Landing — what a signed-out user sees first: the WeatherGPT mark over the
// persona's painted scene, what the app does, and the ways in (create an
// account / sign in / continue as a guest). main.dart shows it whenever AuthStore is signed
// out, so signing out lands back here.
import 'package:flutter/material.dart';

import '../components/app_shell.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../persona_theme.dart';
import '../theme.dart';
import 'auth_page.dart';

class LandingPage extends StatelessWidget {
  const LandingPage({super.key});

  static const _features = [
    (Icons.wb_sunny_outlined, 'Live forecast', "Today, tonight and tomorrow for your city."),
    (Icons.fact_check_outlined, 'Answers with evidence', 'Every number is checked against the source data.'),
    (Icons.warning_amber_rounded, 'IMD warnings', "The colour-coded warning, verbatim — never re-graded."),
    (Icons.translate, 'Five languages & voice', 'English, हिन्दी, தமிழ், తెలుగు, मराठी — type or speak.'),
  ];

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    void open(AuthMode mode) =>
        Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => AuthPage(initialMode: mode)));

    return Scaffold(
      backgroundColor: t.skyBottom,
      body: DecoratedBox(
        decoration: BoxDecoration(gradient: t.skyGradient),
        child: SafeArea(
          bottom: false,
          child: LayoutBuilder(
            builder: (context, constraints) => SingleChildScrollView(
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: IntrinsicHeight(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(AppSpace.lg, AppSpace.lg, AppSpace.lg, 0),
                        child: Row(
                          children: [
                            const BrandMark(size: 40),
                            const SizedBox(width: 10),
                            Text(
                              'WeatherGPT',
                              style: AppText.headlineLg.copyWith(color: t.ink, fontWeight: FontWeight.w800),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 150, child: PersonaScenery(SceneSlot.header)),
                      Expanded(
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: t.sheet,
                            borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.sheet)),
                            boxShadow: [
                              BoxShadow(
                                color: t.shadow.withValues(alpha: 0.06),
                                blurRadius: 16,
                                offset: const Offset(0, -2),
                              ),
                            ],
                          ),
                          child: Padding(
                            padding: EdgeInsets.fromLTRB(
                              AppSpace.lg,
                              AppSpace.lg + 4,
                              AppSpace.lg,
                              AppSpace.lg + MediaQuery.paddingOf(context).bottom,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Text(
                                  'Weather answers\nyou can trust.',
                                  style: AppText.headlineXl.copyWith(color: t.ink, fontSize: 32, height: 1.15),
                                ),
                                const SizedBox(height: AppSpace.sm),
                                Text(
                                  'Ask about rain, heat or wind for your city and get a plain answer — '
                                  'grounded in live data, framed for how you work.',
                                  style: AppText.bodyMd.copyWith(color: t.inkMuted),
                                ),
                                const SizedBox(height: AppSpace.lg),
                                for (final (icon, title, body) in _features) ...[
                                  _Feature(icon: icon, title: title, body: body),
                                  const SizedBox(height: 12),
                                ],
                                const Spacer(),
                                const SizedBox(height: AppSpace.md),
                                GradientButton(
                                  label: 'Create account',
                                  icon: Icons.arrow_forward_rounded,
                                  onPressed: () => open(AuthMode.signUp),
                                ),
                                const SizedBox(height: 12),
                                OutlineActionButton(
                                  label: 'I already have an account',
                                  onPressed: () => open(AuthMode.signIn),
                                ),
                                const SizedBox(height: AppSpace.sm),
                                const GuestButton(),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Feature extends StatelessWidget {
  final IconData icon;
  final String title;
  final String body;
  const _Feature({required this.icon, required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(color: t.tint, borderRadius: BorderRadius.circular(AppRadius.xl)),
          child: Icon(icon, size: 21, color: t.primary),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: AppText.labelMd.copyWith(color: t.ink, fontWeight: FontWeight.w700, fontSize: 14),
              ),
              Text(body, style: AppText.bodySm.copyWith(color: t.inkMuted)),
            ],
          ),
        ),
      ],
    );
  }
}
