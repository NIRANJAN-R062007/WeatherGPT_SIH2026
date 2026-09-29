// Profile — opened from the drawer's "Profile" item: the signed-in account's
// details (name, email, phone, occupation from the Supabase account's
// user_metadata), the active persona, and Sign out. Signing out clears the
// saved session and returns to the landing page. A guest sees an invitation
// to sign in or create an account instead, and "Exit guest mode".
import 'package:flutter/material.dart';

import '../auth_client.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../persona_theme.dart';
import '../state/auth_store.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import 'auth_page.dart';
import 'persona_page.dart';

Future<void> openProfile(BuildContext context) {
  return Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const ProfilePage()));
}

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

String _memberSince(DateTime? d) {
  if (d == null) return '—';
  final local = d.toLocal();
  return '${local.day} ${_months[local.month - 1]} ${local.year}';
}

/// "+919876543210" / "9876543210" → "+91 98765 43210" / "98765 43210".
String formatPhone(String raw) {
  final digits = raw.replaceAll(RegExp(r'[^0-9]'), '');
  if (digits.length == 10) return '${digits.substring(0, 5)} ${digits.substring(5)}';
  if (digits.length == 12 && digits.startsWith('91')) {
    return '+91 ${digits.substring(2, 7)} ${digits.substring(7)}';
  }
  return raw;
}

Future<void> confirmSignOut(BuildContext context) async {
  final t = PersonaTheme.of(context);
  final ok = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text('Sign out?', style: AppText.headlineSm.copyWith(color: t.ink)),
      content: Text(
        "You'll need your email and password to sign in again.",
        style: AppText.bodyMd.copyWith(color: t.inkMuted),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Cancel')),
        TextButton(
          style: TextButton.styleFrom(foregroundColor: AppColors.error),
          onPressed: () => Navigator.of(dialogContext).pop(true),
          child: const Text('Sign out'),
        ),
      ],
    ),
  );
  if (ok != true || !context.mounted) return;
  final auth = AuthStore.read(context);
  Navigator.of(context).popUntil((r) => r.isFirst);
  await auth.signOut();
}

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final auth = AuthStore.of(context);
    final user = auth.user;
    final persona = UiPrefs.of(context).personaInfo;
    if (auth.isGuest) return const _GuestProfile();
    // Signed out underneath us (the page is closing).
    if (user == null) return const SubPageScaffold(body: SizedBox.shrink());
    String orNone(String v) => v.isEmpty ? 'Not added' : v;

    return SubPageScaffold(
      body: PageFrame(
        showCityPill: false,
        children: [
          Text(
            'Profile',
            style: AppText.headlineLg.copyWith(color: t.ink, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: AppSpace.md),
          _Hero(user: user),
          const SizedBox(height: AppSpace.lg),
          const SectionTitle('Account details'),
          const SizedBox(height: AppSpace.sm),
          _DetailRow(icon: Icons.mail_outline, label: 'Email', value: user.email),
          _DetailRow(icon: Icons.phone_outlined, label: 'Phone', value: orNone(formatPhone(user.phone))),
          _DetailRow(icon: Icons.work_outline, label: 'Occupation', value: orNone(user.occupation)),
          _DetailRow(icon: Icons.event_outlined, label: 'Member since', value: _memberSince(user.createdAt)),
          const SizedBox(height: AppSpace.md),
          const SectionTitle('Persona'),
          const SizedBox(height: AppSpace.sm),
          ActionRow(
            leading: IconDisc(persona.icon, solid: true),
            title: persona.label,
            subtitle: persona.tagline,
            onTap: () => openPersonaPicker(context),
          ),
          const SizedBox(height: AppSpace.xl),
          OutlineActionButton(
            label: 'Sign out',
            icon: Icons.logout_rounded,
            destructive: true,
            onPressed: () => confirmSignOut(context),
          ),
        ],
      ),
    );
  }
}

/// A guest's Profile: what an account adds, and the ways to get one.
class _GuestProfile extends StatelessWidget {
  const _GuestProfile();

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final persona = UiPrefs.of(context).personaInfo;
    void open(AuthMode mode) =>
        Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => AuthPage(initialMode: mode)));
    return SubPageScaffold(
      body: PageFrame(
        showCityPill: false,
        children: [
          Text(
            'Profile',
            style: AppText.headlineLg.copyWith(color: t.ink, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: AppSpace.md),
          AppCard(
            wash: true,
            padding: const EdgeInsets.all(AppSpace.lg),
            child: Row(
              children: [
                const GuestAvatar(size: 68),
                const SizedBox(width: AppSpace.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Guest',
                        style: AppText.headlineMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        "You're using WeatherGPT without an account.",
                        style: AppText.bodySm.copyWith(color: t.inkMuted),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpace.lg),
          const SectionTitle('With an account'),
          const SizedBox(height: AppSpace.sm),
          for (final (icon, text) in const [
            (Icons.badge_outlined, 'Your name, phone and occupation on your profile'),
            (Icons.devices_outlined, 'The same profile on any phone you sign in on'),
          ])
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpace.sm),
              child: ActionRow(icon: icon, title: text, trailing: const SizedBox.shrink()),
            ),
          const SizedBox(height: AppSpace.md),
          const SectionTitle('Persona'),
          const SizedBox(height: AppSpace.sm),
          ActionRow(
            leading: IconDisc(persona.icon, solid: true),
            title: persona.label,
            subtitle: persona.tagline,
            onTap: () => openPersonaPicker(context),
          ),
          const SizedBox(height: AppSpace.xl),
          GradientButton(label: 'Create account', onPressed: () => open(AuthMode.signUp)),
          const SizedBox(height: 12),
          OutlineActionButton(label: 'Sign in', onPressed: () => open(AuthMode.signIn)),
          const SizedBox(height: 12),
          OutlineActionButton(
            label: 'Exit guest mode',
            icon: Icons.logout_rounded,
            destructive: true,
            onPressed: () {
              final auth = AuthStore.read(context);
              Navigator.of(context).popUntil((r) => r.isFirst);
              auth.signOut();
            },
          ),
        ],
      ),
    );
  }
}

/// The guest's avatar: the accent disc with a person outline.
class GuestAvatar extends StatelessWidget {
  final double size;
  const GuestAvatar({super.key, this.size = 44});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: t.accentGradient,
        shape: BoxShape.circle,
        border: Border.all(color: t.card, width: size > 50 ? 3 : 2),
        boxShadow: t.cardShadow,
      ),
      child: Icon(Icons.person_outline, size: size * 0.55, color: t.onPrimary),
    );
  }
}

/// Initials avatar, name, email and an occupation chip on a washed card.
class _Hero extends StatelessWidget {
  final AuthUser user;
  const _Hero({required this.user});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return AppCard(
      wash: true,
      padding: const EdgeInsets.all(AppSpace.lg),
      child: Row(
        children: [
          ProfileAvatar(user: user, size: 68),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user.displayName,
                  style: AppText.headlineMd.copyWith(color: t.ink, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 2),
                Text(
                  user.email,
                  style: AppText.bodySm.copyWith(color: t.inkMuted),
                  overflow: TextOverflow.ellipsis,
                ),
                if (user.occupation.isNotEmpty) ...[
                  const SizedBox(height: AppSpace.sm),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(color: t.card, borderRadius: BorderRadius.circular(999)),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.work_outline, size: 14, color: t.primary),
                        const SizedBox(width: 5),
                        Flexible(
                          child: Text(
                            user.occupation,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The accent-gradient disc with the user's initials.
class ProfileAvatar extends StatelessWidget {
  final AuthUser user;
  final double size;
  const ProfileAvatar({super.key, required this.user, this.size = 44});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: t.accentGradient,
        shape: BoxShape.circle,
        border: Border.all(color: t.card, width: size > 50 ? 3 : 2),
        boxShadow: t.cardShadow,
      ),
      child: Text(
        user.initials,
        style: AppText.headlineSm.copyWith(color: t.onPrimary, fontSize: size * 0.36, fontWeight: FontWeight.w700),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _DetailRow({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.sm),
      child: MergeSemantics(
        child: ActionRow(icon: icon, title: label, subtitle: value, trailing: const SizedBox.shrink()),
      ),
    );
  }
}
