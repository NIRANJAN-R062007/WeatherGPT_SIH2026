// Sign in / create account, against the team's Supabase project
// (auth_client.dart). Creating an account collects the profile the drawer's
// Profile page shows: name, email, phone and occupation. The project
// requires email confirmation, so a new account ends on a "check your inbox"
// step with a resend button; signing in to an unconfirmed account offers the
// same resend. Success flips AuthStore to signed in, and main.dart swaps the
// onboarding pages for the app.
import 'package:flutter/material.dart';

import '../auth_client.dart';
import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../components/surfaces.dart';
import '../persona_theme.dart';
import '../state/auth_store.dart';
import '../theme.dart';
import 'reset_password_page.dart';
import '../i18n.dart';

enum AuthMode { signIn, signUp }

final RegExp _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

/// Digits only, keeping a leading +; spaces, dashes and brackets dropped.
String normalizePhone(String raw) {
  final trimmed = raw.trim();
  final digits = trimmed.replaceAll(RegExp(r'[^0-9]'), '');
  return trimmed.startsWith('+') ? '+$digits' : digits;
}

String? validateEmail(String? v) {
  final s = (v ?? '').trim();
  if (s.isEmpty) return 'Enter your email.';
  if (!_emailPattern.hasMatch(s)) return 'That doesn\'t look like an email address.';
  return null;
}

String? validatePhone(String? v) {
  final s = normalizePhone(v ?? '');
  if (s.isEmpty) return 'Enter your phone number.';
  final digits = s.replaceAll('+', '');
  if (digits.length < 10 || digits.length > 15) {
    return 'Enter a 10-digit mobile number (with country code if outside India).';
  }
  return null;
}

String? validateOccupation(String? v) {
  final s = (v ?? '').trim();
  if (s.isEmpty) return 'Enter your occupation.';
  if (s.length > 60) return 'Keep it under 60 characters.';
  return null;
}

String? validateNewPassword(String? v) {
  final s = v ?? '';
  if (s.isEmpty) return 'Enter a password.';
  if (s.length < 8) return 'Use at least 8 characters.';
  return null;
}

class AuthPage extends StatefulWidget {
  final AuthMode initialMode;
  const AuthPage({super.key, this.initialMode = AuthMode.signIn});

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _occupation = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();

  late AuthMode _mode = widget.initialMode;
  bool _busy = false;
  bool _showPassword = false;
  String? _error;
  bool _offerResend = false;
  String? _notice;

  /// Set once an account is created and waits for its confirmation link.
  String? _awaitingConfirmation;

  static const _occupations = ['Farmer', 'Fisherman', 'Pilot', 'City official', 'Student', 'Teacher'];

  @override
  void dispose() {
    for (final c in [_name, _email, _phone, _occupation, _password, _confirm]) {
      c.dispose();
    }
    super.dispose();
  }

  void _switchMode(AuthMode mode) {
    setState(() {
      _mode = mode;
      _error = null;
      _notice = null;
      _offerResend = false;
      _awaitingConfirmation = null;
    });
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!(_form.currentState?.validate() ?? false)) return;
    final auth = AuthStore.read(context);
    final navigator = Navigator.of(context);
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
      _offerResend = false;
    });
    try {
      if (_mode == AuthMode.signIn) {
        await auth.signIn(_email.text, _password.text);
        navigator.popUntil((r) => r.isFirst);
        return;
      }
      final result = await auth.signUp(
        email: _email.text,
        password: _password.text,
        fullName: _name.text,
        phone: normalizePhone(_phone.text),
        occupation: _occupation.text,
      );
      if (!result.needsConfirmation) {
        navigator.popUntil((r) => r.isFirst);
        return;
      }
      if (mounted) setState(() => _awaitingConfirmation = result.email);
    } on AuthError catch (e) {
      if (mounted) {
        setState(() {
          _error = tr(context, e.message, e.args);
          _offerResend = e.emailNotConfirmed;
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resend(String email) async {
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      await AuthStore.read(context).resendConfirmation(email);
      if (mounted) setState(() => _notice = tr(context, 'Confirmation email sent again to {email}.', {'email': email}));
    } on AuthError catch (e) {
      if (mounted) setState(() => _error = tr(context, e.message, e.args));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final signUp = _mode == AuthMode.signUp;
    final awaiting = _awaitingConfirmation;
    return SubPageScaffold(
      body: PageFrame(
        showCityPill: false,
        footer: SceneryFooter.soft,
        children: awaiting != null ? _confirmation(awaiting) : _formBody(signUp),
      ),
    );
  }

  List<Widget> _formBody(bool signUp) {
    final t = PersonaTheme.of(context);
    Widget gap([double h = 14]) => SizedBox(height: h);
    final passwordToggle = IconButton(
      tooltip: tr(context, _showPassword ? 'Hide password' : 'Show password'),
      icon: Icon(_showPassword ? Icons.visibility_off_outlined : Icons.visibility_outlined, color: t.inkMuted),
      onPressed: () => setState(() => _showPassword = !_showPassword),
    );

    return [
      PageHeader(
        title: signUp ? 'Create your account' : 'Welcome back',
        subtitle: signUp
            ? 'Tell us a little about you — it appears on your profile.'
            : 'Sign in to continue to WeatherGPT.',
      ),
      const SizedBox(height: AppSpace.lg),
      Form(
        key: _form,
        child: AutofillGroup(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (signUp) ...[
                AppTextField(
                  controller: _name,
                  label: 'Full name',
                  icon: Icons.person_outline,
                  capitalization: TextCapitalization.words,
                  autofillHints: const [AutofillHints.name],
                  enabled: !_busy,
                  validator: (v) => (v ?? '').trim().isEmpty ? 'Enter your name.' : null,
                ),
                gap(),
              ],
              AppTextField(
                controller: _email,
                label: 'Email',
                icon: Icons.mail_outline,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                enabled: !_busy,
                validator: validateEmail,
              ),
              gap(),
              if (signUp) ...[
                AppTextField(
                  controller: _phone,
                  label: 'Phone number',
                  hint: '98765 43210',
                  icon: Icons.phone_outlined,
                  keyboardType: TextInputType.phone,
                  autofillHints: const [AutofillHints.telephoneNumber],
                  enabled: !_busy,
                  validator: validatePhone,
                ),
                gap(),
                AppTextField(
                  controller: _occupation,
                  label: 'Occupation',
                  hint: 'e.g. Farmer, Pilot, Student',
                  icon: Icons.work_outline,
                  capitalization: TextCapitalization.sentences,
                  enabled: !_busy,
                  validator: validateOccupation,
                ),
                gap(8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final o in _occupations.map((o) => tr(context, o)))
                      _SuggestionChip(
                        label: o,
                        selected: _occupation.text.trim().toLowerCase() == o.toLowerCase(),
                        onTap: _busy ? null : () => setState(() => _occupation.text = o),
                      ),
                  ],
                ),
                gap(),
              ],
              AppTextField(
                controller: _password,
                label: 'Password',
                icon: Icons.lock_outline,
                obscure: !_showPassword,
                suffix: passwordToggle,
                textInputAction: signUp ? TextInputAction.next : TextInputAction.done,
                autofillHints: [signUp ? AutofillHints.newPassword : AutofillHints.password],
                enabled: !_busy,
                onSubmitted: signUp ? null : (_) => _submit(),
                validator: (v) {
                  final s = v ?? '';
                  if (s.isEmpty) return 'Enter your password.';
                  if (signUp && s.length < 8) return 'Use at least 8 characters.';
                  return null;
                },
              ),
              if (!signUp)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: _busy
                        ? null
                        : () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => ResetPasswordPage(initialEmail: _email.text.trim()),
                            ),
                          ),
                    child: Text(
                      tr(context, 'Forgot password?'),
                      style: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
              if (signUp) ...[
                gap(),
                AppTextField(
                  controller: _confirm,
                  label: 'Confirm password',
                  icon: Icons.lock_outline,
                  obscure: !_showPassword,
                  textInputAction: TextInputAction.done,
                  enabled: !_busy,
                  onSubmitted: (_) => _submit(),
                  validator: (v) => v != _password.text ? "Passwords don't match." : null,
                ),
              ],
            ],
          ),
        ),
      ),
      if (_error != null) ...[
        const SizedBox(height: AppSpace.md),
        FormMessage(text: _error!, error: true),
        if (_offerResend) ...[
          const SizedBox(height: AppSpace.sm),
          OutlineActionButton(
            label: 'Resend confirmation email',
            icon: Icons.forward_to_inbox_outlined,
            onPressed: _busy ? null : () => _resend(_email.text.trim()),
          ),
        ],
      ],
      if (_notice != null) ...[const SizedBox(height: AppSpace.md), FormMessage(text: _notice!)],
      const SizedBox(height: AppSpace.lg),
      GradientButton(label: signUp ? 'Create account' : 'Sign in', loading: _busy, onPressed: _submit),
      const SizedBox(height: 12),
      GoogleSignInButton(enabled: !_busy),
      const SizedBox(height: AppSpace.md),
      Center(
        child: Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              '${tr(context, signUp ? 'Already have an account?' : 'New to WeatherGPT?')} ',
              style: AppText.bodyMd.copyWith(color: t.inkMuted),
            ),
            InkWell(
              borderRadius: BorderRadius.circular(AppRadius.lg),
              onTap: _busy ? null : () => _switchMode(signUp ? AuthMode.signIn : AuthMode.signUp),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
                child: Text(
                  tr(context, signUp ? 'Sign in' : 'Create an account'),
                  style: AppText.labelMd.copyWith(color: t.primary, fontWeight: FontWeight.w700, fontSize: 14),
                ),
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: AppSpace.xs),
      GuestButton(enabled: !_busy),
    ];
  }

  List<Widget> _confirmation(String email) {
    final t = PersonaTheme.of(context);
    return [
      const SizedBox(height: AppSpace.md),
      const Center(child: IconDisc(Icons.mark_email_unread_outlined, solid: true, size: 72)),
      const SizedBox(height: AppSpace.lg),
      Text(
        tr(context, 'Confirm your email'),
        textAlign: TextAlign.center,
        style: AppText.headlineLg.copyWith(color: t.ink, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: AppSpace.sm),
      Text.rich(
        TextSpan(
          children: [
            // "{email}" in the translated sentence is set in bold.
            for (final (i, part) in tr(
              context,
              'We sent a confirmation link to {email}. Open it, then come back and sign in.',
            ).split('{email}').indexed) ...[
              if (i > 0)
                TextSpan(
                  text: email,
                  style: TextStyle(color: t.ink, fontWeight: FontWeight.w700),
                ),
              TextSpan(text: part),
            ],
          ],
        ),
        textAlign: TextAlign.center,
        style: AppText.bodyMd.copyWith(color: t.inkMuted),
      ),
      const SizedBox(height: AppSpace.sm),
      Text(
        tr(
          context,
          "Can't find it? Check Spam and Promotions. Some school and work email systems block our mail — if nothing arrives in a few minutes, sign up with a personal email instead.",
        ),
        textAlign: TextAlign.center,
        style: AppText.bodySm.copyWith(color: t.inkMuted),
      ),
      if (_error != null) ...[const SizedBox(height: AppSpace.md), FormMessage(text: _error!, error: true)],
      if (_notice != null) ...[const SizedBox(height: AppSpace.md), FormMessage(text: _notice!)],
      const SizedBox(height: AppSpace.xl),
      GradientButton(
        label: "I've confirmed — sign in",
        onPressed: _busy
            ? null
            : () {
                _password.clear();
                _switchMode(AuthMode.signIn);
              },
      ),
      const SizedBox(height: 12),
      OutlineActionButton(
        label: 'Resend email',
        icon: Icons.forward_to_inbox_outlined,
        onPressed: _busy ? null : () => _resend(email),
      ),
    ];
  }
}

class _SuggestionChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  const _SuggestionChip({required this.label, required this.selected, this.onTap});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    return Material(
      color: selected ? t.primary : t.tint,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Text(
            label,
            style: AppText.labelMd.copyWith(color: selected ? t.onPrimary : t.primary, fontWeight: FontWeight.w600),
          ),
        ),
      ),
    );
  }
}

/// An inline error (red) or notice (persona tint) under the form.
class FormMessage extends StatelessWidget {
  final String text;
  final bool error;
  const FormMessage({super.key, required this.text, this.error = false});

  @override
  Widget build(BuildContext context) {
    final t = PersonaTheme.of(context);
    final fg = error ? AppColors.onErrorContainer : t.ink;
    return Semantics(
      liveRegion: true,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: error ? AppColors.errorContainer : t.tint,
          borderRadius: BorderRadius.circular(AppRadius.xl),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(error ? Icons.error_outline : Icons.check_circle_outline, size: 18, color: error ? fg : t.primary),
            const SizedBox(width: 8),
            Expanded(
              child: Text(tr(context, text), style: AppText.bodyMd.copyWith(color: fg)),
            ),
          ],
        ),
      ),
    );
  }
}
