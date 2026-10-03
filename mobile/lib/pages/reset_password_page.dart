// Forgot password, from the sign-in form. Two steps, no deep link: Supabase
// mails a 6-digit code, the user types it here with a new password, and a
// correct code signs them in. The code only appears in the mail once the
// project's "Reset password" template includes {{ .Token }} (dashboard).
import 'package:flutter/material.dart';

import '../auth_client.dart';
import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../persona_theme.dart';
import '../state/auth_store.dart';
import '../theme.dart';
import 'auth_page.dart';
import '../i18n.dart';

class ResetPasswordPage extends StatefulWidget {
  final String initialEmail;
  const ResetPasswordPage({super.key, this.initialEmail = ''});

  @override
  State<ResetPasswordPage> createState() => _ResetPasswordPageState();
}

class _ResetPasswordPageState extends State<ResetPasswordPage> {
  final _emailForm = GlobalKey<FormState>();
  final _resetForm = GlobalKey<FormState>();
  late final _email = TextEditingController(text: widget.initialEmail);
  final _code = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();

  bool _busy = false;
  bool _showPassword = false;
  bool _codeSent = false;
  String? _error;
  String? _notice;

  @override
  void dispose() {
    for (final c in [_email, _code, _password, _confirm]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      await action();
    } on AuthError catch (e) {
      if (mounted) setState(() => _error = tr(context, e.message, e.args));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _sendCode() async {
    if (!(_emailForm.currentState?.validate() ?? false)) return;
    final auth = AuthStore.read(context);
    await _run(() async {
      await auth.sendPasswordReset(_email.text);
      if (mounted) {
        setState(() {
          _codeSent = true;
          _notice = tr(context, 'We sent a reset code to {email}.', {'email': _email.text.trim()});
        });
      }
    });
  }

  Future<void> _reset() async {
    if (!(_resetForm.currentState?.validate() ?? false)) return;
    final auth = AuthStore.read(context);
    final navigator = Navigator.of(context);
    await _run(() async {
      await auth.resetPassword(email: _email.text, code: _code.text, newPassword: _password.text);
      navigator.popUntil((r) => r.isFirst);
    });
  }

  @override
  Widget build(BuildContext context) {
    return SubPageScaffold(
      body: PageFrame(
        showCityPill: false,
        footer: SceneryFooter.soft,
        children: [
          PageHeader(
            title: 'Reset your password',
            subtitle: _codeSent
                ? 'Enter the code from the email and choose a new password.'
                : "Enter your account's email and we'll send you a reset code.",
          ),
          const SizedBox(height: AppSpace.lg),
          if (_codeSent) ..._resetStep() else ..._emailStep(),
        ],
      ),
    );
  }

  List<Widget> _messages() => [
    if (_error != null) ...[const SizedBox(height: AppSpace.md), FormMessage(text: _error!, error: true)],
    if (_notice != null) ...[const SizedBox(height: AppSpace.md), FormMessage(text: _notice!)],
  ];

  List<Widget> _emailStep() => [
    Form(
      key: _emailForm,
      child: AppTextField(
        controller: _email,
        label: 'Email',
        icon: Icons.mail_outline,
        keyboardType: TextInputType.emailAddress,
        autofillHints: const [AutofillHints.email],
        textInputAction: TextInputAction.done,
        enabled: !_busy,
        validator: validateEmail,
        onSubmitted: (_) => _sendCode(),
      ),
    ),
    ..._messages(),
    const SizedBox(height: AppSpace.lg),
    GradientButton(label: 'Send reset code', loading: _busy, onPressed: _sendCode),
  ];

  List<Widget> _resetStep() {
    final t = PersonaTheme.of(context);
    Widget gap() => const SizedBox(height: 14);
    return [
      Form(
        key: _resetForm,
        child: AutofillGroup(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              AppTextField(
                controller: _code,
                label: 'Reset code',
                hint: '123456',
                icon: Icons.pin_outlined,
                keyboardType: TextInputType.number,
                autofillHints: const [AutofillHints.oneTimeCode],
                enabled: !_busy,
                validator: (v) {
                  final s = (v ?? '').trim();
                  if (s.isEmpty) return 'Enter the code from the email.';
                  if (!RegExp(r'^\d{6,10}$').hasMatch(s)) return 'The code is the digits from the email.';
                  return null;
                },
              ),
              gap(),
              AppTextField(
                controller: _password,
                label: 'New password',
                icon: Icons.lock_outline,
                obscure: !_showPassword,
                suffix: IconButton(
                  tooltip: tr(context, _showPassword ? 'Hide password' : 'Show password'),
                  icon: Icon(
                    _showPassword ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                    color: t.inkMuted,
                  ),
                  onPressed: () => setState(() => _showPassword = !_showPassword),
                ),
                autofillHints: const [AutofillHints.newPassword],
                enabled: !_busy,
                validator: validateNewPassword,
              ),
              gap(),
              AppTextField(
                controller: _confirm,
                label: 'Confirm new password',
                icon: Icons.lock_outline,
                obscure: !_showPassword,
                textInputAction: TextInputAction.done,
                enabled: !_busy,
                onSubmitted: (_) => _reset(),
                validator: (v) => v != _password.text ? "Passwords don't match." : null,
              ),
            ],
          ),
        ),
      ),
      ..._messages(),
      const SizedBox(height: AppSpace.lg),
      GradientButton(label: 'Set new password', loading: _busy, onPressed: _reset),
      const SizedBox(height: 12),
      OutlineActionButton(
        label: 'Send a new code',
        icon: Icons.forward_to_inbox_outlined,
        onPressed: _busy
            ? null
            : () {
                final auth = AuthStore.read(context);
                _run(() async {
                  await auth.sendPasswordReset(_email.text);
                  if (mounted) {
                    setState(
                      () =>
                          _notice = tr(context, 'A new code is on its way to {email}.', {'email': _email.text.trim()}),
                    );
                  }
                });
              },
      ),
    ];
  }
}
