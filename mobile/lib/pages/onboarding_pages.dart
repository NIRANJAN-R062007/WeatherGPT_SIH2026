// Onboarding — what a signed-out user sees (pics/ Languages and Welcome
// mockups, in their light and dark designs):
//   1. LanguagePage: pick English / हिन्दी / தமிழ் / తెలుగు / मराठी, then
//      Continue. The pick becomes the app language (UiPrefs.lang).
//   2. WelcomeLoginPage: the WeatherGPT logo and "Welcome to WeatherGPT!"
//      over the painted panorama, and the log-in sheet under it — email and
//      password, Google, Sign Up and Sign in as Guest — all in the language
//      picked on page 1.
// main.dart shows LanguagePage whenever AuthStore is signed out, so signing
// out lands back here. Sign Up and Forgot password open the existing
// auth_page.dart / reset_password_page.dart.
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../auth_client.dart';
import '../components/common.dart';
import '../components/forms.dart';
import '../components/onboarding_scene.dart';
import '../config.dart';
import '../onboarding_strings.dart';
import '../state/auth_store.dart';
import '../state/ui_prefs.dart';
import '../theme.dart';
import 'auth_page.dart';
import 'reset_password_page.dart';

const double _maxWidth = 460;

/// Back arrow (when there is somewhere to go back to) and the light / dark
/// toggle — the only way to switch modes before signing in.
class _OnbTopBar extends StatelessWidget {
  final bool showBack;
  const _OnbTopBar({this.showBack = false});

  @override
  Widget build(BuildContext context) {
    final p = OnbPalette.of(context);
    final prefs = UiPrefs.of(context);
    final s = OnboardingStrings.of(prefs.lang);
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          if (showBack)
            IconButton(
              tooltip: s.back,
              icon: Icon(Icons.arrow_back_ios_new_rounded, size: 22, color: p.ink),
              onPressed: () => Navigator.of(context).maybePop(),
            ),
          const Spacer(),
          IconButton(
            tooltip: p.isDark ? s.lightMode : s.darkMode,
            icon: Icon(p.isDark ? Icons.light_mode_outlined : Icons.dark_mode_outlined, size: 24, color: p.ink),
            onPressed: () => prefs.appearance = p.isDark ? Appearance.light : Appearance.dark,
          ),
        ],
      ),
    );
  }
}

/// The full-width blue button.
class _OnbButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool loading;
  const _OnbButton({required this.label, this.icon, this.onPressed, this.loading = false});

  @override
  Widget build(BuildContext context) {
    final p = OnbPalette.of(context);
    final radius = BorderRadius.circular(16);
    return Semantics(
      button: true,
      enabled: onPressed != null && !loading,
      label: label,
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: p.button,
          borderRadius: radius,
          boxShadow: [
            BoxShadow(color: p.buttonBottom.withValues(alpha: 0.3), blurRadius: 14, offset: const Offset(0, 5)),
          ],
        ),
        child: Material(
          color: Colors.transparent,
          borderRadius: radius,
          child: InkWell(
            borderRadius: radius,
            onTap: loading ? null : onPressed,
            child: SizedBox(
              height: 54,
              child: Center(
                child: loading
                    ? InlineSpinner(size: 22, color: Colors.white, track: Colors.white.withValues(alpha: 0.35))
                    : Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Flexible(
                            child: Text(
                              label,
                              overflow: TextOverflow.ellipsis,
                              style: AppText.labelMd.copyWith(
                                color: Colors.white,
                                fontSize: 17,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          if (icon != null) ...[const SizedBox(width: 10), Icon(icon, size: 22, color: Colors.white)],
                        ],
                      ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The logo mark: the saved pics/ logos (weathergpt-logo-light.svg for light,
/// weathergpt-logo-original.svg for dark) without their "WeatherGPT" text.
class _Logo extends StatelessWidget {
  final double size;
  const _Logo({required this.size});

  @override
  Widget build(BuildContext context) => Center(
    child: Image.asset(
      OnbPalette.of(context).isDark
          ? 'assets/branding/weathergpt-onboarding-dark.png'
          : 'assets/branding/weathergpt-onboarding-light.png',
      width: size,
      height: size,
      filterQuality: FilterQuality.medium,
      excludeFromSemantics: true,
    ),
  );
}

// --------------------------------------------------------------------------
// 1. Languages

class LanguagePage extends StatefulWidget {
  const LanguagePage({super.key});

  @override
  State<LanguagePage> createState() => _LanguagePageState();
}

class _LanguagePageState extends State<LanguagePage> {
  /// English unless a language was picked earlier in this run.
  late String _lang = UiPrefs.read(context).lang;

  void _continue() {
    UiPrefs.read(context).lang = _lang;
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const WelcomeLoginPage()));
  }

  @override
  Widget build(BuildContext context) {
    final p = OnbPalette.of(context);
    final s = OnboardingStrings.of(_lang);
    return Scaffold(
      backgroundColor: p.bgBottom,
      body: DecoratedBox(
        decoration: BoxDecoration(gradient: p.background),
        child: Stack(
          children: [
            Positioned(top: 0, left: 0, right: 0, height: 300, child: CustomPaint(painter: OnboardingCloudsPainter(p))),
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              height: 130,
              child: CustomPaint(painter: OnboardingFooterPainter(p)),
            ),
            SafeArea(
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: _maxWidth),
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(AppSpace.lg, 0, AppSpace.lg, 120),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const _OnbTopBar(),
                        const _Logo(size: 84),
                        const SizedBox(height: 6),
                        Center(child: _Wordmark(p: p, size: 30)),
                        const SizedBox(height: 26),
                        Text(
                          s.languagesTitle,
                          style: AppText.headlineXl.copyWith(
                            color: p.ink,
                            fontSize: 34,
                            height: 1.15,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          s.languagesLead,
                          style: AppText.bodyLg.copyWith(
                            color: p.isDark ? p.accent : p.muted,
                            fontSize: 17,
                            height: 1.35,
                          ),
                        ),
                        const SizedBox(height: 22),
                        for (final MapEntry(key: code, value: label) in kLanguageLabels.entries) ...[
                          _LanguageOption(
                            label: label,
                            selected: code == _lang,
                            onTap: () => setState(() => _lang = code),
                          ),
                          const SizedBox(height: 12),
                        ],
                        const SizedBox(height: 18),
                        _OnbButton(label: s.continueLabel, icon: Icons.arrow_forward_rounded, onPressed: _continue),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// "WeatherGPT!" set as text, the "!" black on light and white on dark.
class _Wordmark extends StatelessWidget {
  final OnbPalette p;
  final double size;
  final String suffix;
  const _Wordmark({required this.p, required this.size, this.suffix = '!'});

  @override
  Widget build(BuildContext context) {
    final base = AppText.headlineXl.copyWith(
      color: p.ink,
      fontSize: size,
      height: 1.15,
      fontWeight: FontWeight.w800,
      letterSpacing: -0.5,
    );
    // Two Texts, not one: a fallback-font script after the brand measures
    // wrong inside a single paragraph and wraps or clips.
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        Text('WeatherGPT', style: base),
        if (suffix.isNotEmpty)
          Text(suffix, style: base.copyWith(color: suffix == '!' ? (p.isDark ? Colors.white : Colors.black) : p.ink)),
      ],
    );
  }
}

class _LanguageOption extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _LanguageOption({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final p = OnbPalette.of(context);
    final radius = BorderRadius.circular(16);
    return Semantics(
      selected: selected,
      inMutuallyExclusiveGroup: true,
      child: Material(
        color: selected ? p.selectedFill : p.field.withValues(alpha: p.isDark ? 0.6 : 0.85),
        shape: RoundedRectangleBorder(
          borderRadius: radius,
          side: BorderSide(color: selected ? p.selectedBorder : p.fieldBorder, width: selected ? 1.6 : 1),
        ),
        child: InkWell(
          borderRadius: radius,
          onTap: onTap,
          child: SizedBox(
            height: 60,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      label,
                      style: AppText.bodyLg.copyWith(color: p.ink, fontSize: 19, fontWeight: FontWeight.w500),
                    ),
                  ),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 160),
                    width: 26,
                    height: 26,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: selected ? p.accent : Colors.transparent,
                      border: selected ? null : Border.all(color: p.radio, width: 1.6),
                    ),
                    child: selected ? const Icon(Icons.check_rounded, size: 18, color: Colors.white) : null,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// --------------------------------------------------------------------------
// 2. Welcome + Log In

final RegExp _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

class WelcomeLoginPage extends StatefulWidget {
  const WelcomeLoginPage({super.key});

  @override
  State<WelcomeLoginPage> createState() => _WelcomeLoginPageState();
}

class _WelcomeLoginPageState extends State<WelcomeLoginPage> {
  final _form = GlobalKey<FormState>();
  final _id = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _showPassword = false;
  String? _error;
  bool _offerResend = false;
  String? _notice;

  @override
  void dispose() {
    _id.dispose();
    _password.dispose();
    super.dispose();
  }

  /// Email, or a phone number — which the project can't sign in with yet
  /// (accounts are email + password; the phone is profile data), so a phone
  /// gets a clear message instead of a failed request.
  String? _validateId(OnboardingStrings s, String? v) {
    final id = (v ?? '').trim();
    if (id.isEmpty) return s.enterEmailOrPhone;
    if (_emailPattern.hasMatch(id)) return null;
    final digits = normalizePhone(id).replaceAll('+', '');
    if (!id.contains('@') && digits.length >= 10 && digits.length <= 15) return s.phoneUnavailable;
    return s.badEmail;
  }

  Future<void> _logIn() async {
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
      await auth.signIn(_id.text, _password.text);
      navigator.popUntil((r) => r.isFirst);
    } on AuthError catch (e) {
      if (mounted) {
        setState(() {
          _error = e.message;
          _offerResend = e.emailNotConfirmed;
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resend(OnboardingStrings s) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthStore.read(context).resendConfirmation(_id.text.trim());
      if (mounted) setState(() => _notice = s.confirmationResent);
    } on AuthError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _guest() {
    final auth = AuthStore.read(context);
    Navigator.of(context).popUntil((r) => r.isFirst);
    auth.continueAsGuest();
  }

  @override
  Widget build(BuildContext context) {
    final p = OnbPalette.of(context);
    final s = OnboardingStrings.of(UiPrefs.of(context).lang);
    final mq = MediaQuery.of(context);
    // The hero is kept compact so the log-in sheet sits high on the screen.
    final heroHeight = mq.padding.top + (mq.size.height > 760 ? 330.0 : 300.0);
    const overlap = 28.0;

    return Scaffold(
      backgroundColor: p.sheet,
      body: LayoutBuilder(
        builder: (context, constraints) => SingleChildScrollView(
          child: Stack(
            children: [
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                height: heroHeight + 4,
                child: DecoratedBox(
                  decoration: BoxDecoration(gradient: p.background),
                  child: CustomPaint(painter: OnboardingScenePainter(p)),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SizedBox(
                    height: heroHeight - overlap,
                    child: Padding(
                      padding: EdgeInsets.only(top: mq.padding.top, left: 4, right: 4),
                      child: Column(
                        children: [
                          const _OnbTopBar(showBack: true),
                          const _Logo(size: 76),
                          const SizedBox(height: 4),
                          _WelcomeTitle(s: s, p: p),
                        ],
                      ),
                    ),
                  ),
                  ConstrainedBox(
                    constraints: BoxConstraints(minHeight: math.max(0, constraints.maxHeight - heroHeight + overlap)),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: p.sheet,
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(30)),
                        border: Border(top: BorderSide(color: p.sheetBorder, width: 1.2)),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: p.isDark ? 0.3 : 0.06),
                            blurRadius: 18,
                            offset: const Offset(0, -4),
                          ),
                        ],
                      ),
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: _maxWidth),
                          child: Padding(
                            padding: EdgeInsets.fromLTRB(22, 26, 22, 20 + mq.padding.bottom),
                            child: _loginForm(s, p),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _loginForm(OnboardingStrings s, OnbPalette p) {
    final linkStyle = AppText.labelMd.copyWith(color: p.accent, fontSize: 14, fontWeight: FontWeight.w700);
    return Form(
      key: _form,
      child: AutofillGroup(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _OnbField(
              controller: _id,
              hint: s.emailOrPhone,
              icon: Icons.mail_outline_rounded,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              enabled: !_busy,
              validator: (v) => _validateId(s, v),
            ),
            const SizedBox(height: 14),
            _OnbField(
              controller: _password,
              hint: s.password,
              icon: Icons.lock_outline_rounded,
              obscure: !_showPassword,
              textInputAction: TextInputAction.done,
              autofillHints: const [AutofillHints.password],
              enabled: !_busy,
              onSubmitted: (_) => _logIn(),
              validator: (v) => (v ?? '').isEmpty ? s.enterPassword : null,
              suffix: IconButton(
                tooltip: _showPassword ? s.hidePassword : s.showPassword,
                icon: Icon(
                  _showPassword ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                  color: p.ink.withValues(alpha: 0.8),
                ),
                onPressed: () => setState(() => _showPassword = !_showPassword),
              ),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: _busy
                    ? null
                    : () => Navigator.of(
                        context,
                      ).push(MaterialPageRoute<void>(builder: (_) => ResetPasswordPage(initialEmail: _id.text.trim()))),
                child: Text(s.forgotPassword, style: linkStyle),
              ),
            ),
            if (_error != null) ...[
              FormMessage(text: _error!, error: true),
              if (_offerResend)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: _busy ? null : () => _resend(s),
                    icon: Icon(Icons.forward_to_inbox_outlined, size: 18, color: p.accent),
                    label: Text(s.resendConfirmation, style: linkStyle),
                  ),
                ),
              const SizedBox(height: 12),
            ],
            if (_notice != null) ...[FormMessage(text: _notice!), const SizedBox(height: 12)],
            _OnbButton(label: s.logIn, loading: _busy, onPressed: _logIn),
            const SizedBox(height: 18),
            Row(
              children: [
                Expanded(child: Divider(color: p.divider, height: 1)),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  child: Text(s.or, style: AppText.bodyMd.copyWith(color: p.muted)),
                ),
                Expanded(child: Divider(color: p.divider, height: 1)),
              ],
            ),
            const SizedBox(height: 18),
            GoogleSignInButton(
              enabled: !_busy,
              builder: (context, onPressed, busy) => _OutlinedPill(
                label: busy ? s.waitingForGoogle : s.continueWithGoogle,
                leading: const GoogleG(size: 22),
                onPressed: onPressed,
              ),
            ),
            const SizedBox(height: 12),
            _GuestButton(label: s.guest, onPressed: _busy ? null : _guest),
            const SizedBox(height: 14),
            Center(
              child: Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                alignment: WrapAlignment.center,
                children: [
                  Text(s.noAccount, style: AppText.bodyMd.copyWith(color: p.muted)),
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => Navigator.of(
                            context,
                          ).push(MaterialPageRoute<void>(builder: (_) => const AuthPage(initialMode: AuthMode.signUp))),
                    child: Text(s.signUp, style: linkStyle.copyWith(fontSize: 15)),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// "Welcome to" / "WeatherGPT!" — or the brand first, for languages where
/// the welcome follows the name (OnboardingStrings.welcome*).
class _WelcomeTitle extends StatelessWidget {
  final OnboardingStrings s;
  final OnbPalette p;
  const _WelcomeTitle({required this.s, required this.p});

  @override
  Widget build(BuildContext context) {
    final small = AppText.headlineLg.copyWith(color: p.ink, fontSize: 24, height: 1.25, fontWeight: FontWeight.w500);
    return Semantics(
      header: true,
      label: s.welcome,
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpace.lg),
        child: Column(
          children: [
            if (s.welcomeBefore.isNotEmpty) Text(s.welcomeBefore, textAlign: TextAlign.center, style: small),
            FittedBox(
              fit: BoxFit.scaleDown,
              child: _Wordmark(p: p, size: 38, suffix: s.welcomeBrandSuffix),
            ),
            if (s.welcomeAfter.isNotEmpty) Text(s.welcomeAfter, textAlign: TextAlign.center, style: small),
          ],
        ),
      ),
    );
  }
}

/// A rounded input with a leading icon and the hint inside, as in the
/// mockup (no floating label).
class _OnbField extends StatelessWidget {
  final TextEditingController controller;
  final String hint;
  final IconData icon;
  final TextInputType? keyboardType;
  final TextInputAction textInputAction;
  final bool obscure;
  final Widget? suffix;
  final Iterable<String>? autofillHints;
  final FormFieldValidator<String>? validator;
  final ValueChanged<String>? onSubmitted;
  final bool enabled;

  const _OnbField({
    required this.controller,
    required this.hint,
    required this.icon,
    this.keyboardType,
    this.textInputAction = TextInputAction.next,
    this.obscure = false,
    this.suffix,
    this.autofillHints,
    this.validator,
    this.onSubmitted,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    final p = OnbPalette.of(context);
    OutlineInputBorder border(Color c, [double w = 1]) => OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: BorderSide(color: c, width: w),
    );
    return TextFormField(
      controller: controller,
      enabled: enabled,
      obscureText: obscure,
      keyboardType: keyboardType,
      textInputAction: textInputAction,
      autofillHints: autofillHints,
      validator: validator,
      onFieldSubmitted: onSubmitted,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      style: AppText.bodyLg.copyWith(color: p.ink, fontSize: 16),
      cursorColor: p.accent,
      decoration: InputDecoration(
        hintText: hint,
        filled: true,
        fillColor: p.field,
        hintStyle: AppText.bodyLg.copyWith(color: p.muted, fontSize: 16),
        prefixIcon: Padding(
          padding: const EdgeInsets.only(left: 16, right: 10),
          child: Icon(icon, size: 24, color: p.ink.withValues(alpha: 0.85)),
        ),
        prefixIconConstraints: const BoxConstraints(minWidth: 50, minHeight: 24),
        suffixIcon: suffix,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 17),
        border: border(p.fieldBorder),
        enabledBorder: border(p.fieldBorder),
        disabledBorder: border(p.fieldBorder),
        focusedBorder: border(p.accent, 1.6),
        errorBorder: border(AppColors.error),
        focusedErrorBorder: border(AppColors.error, 1.6),
        errorStyle: AppText.bodySm.copyWith(color: p.isDark ? const Color(0xFFFFB4AB) : AppColors.error),
        errorMaxLines: 3,
      ),
    );
  }
}

/// The outlined "Continue with Google" button.
class _OutlinedPill extends StatelessWidget {
  final String label;
  final Widget leading;
  final VoidCallback? onPressed;
  const _OutlinedPill({required this.label, required this.leading, this.onPressed});

  @override
  Widget build(BuildContext context) {
    final p = OnbPalette.of(context);
    final radius = BorderRadius.circular(16);
    return Opacity(
      opacity: onPressed == null ? 0.6 : 1,
      child: Material(
        color: p.isDark ? Colors.transparent : p.field,
        shape: RoundedRectangleBorder(
          borderRadius: radius,
          side: BorderSide(color: p.isDark ? p.accent.withValues(alpha: 0.8) : p.fieldBorder, width: 1.3),
        ),
        child: InkWell(
          borderRadius: radius,
          onTap: onPressed,
          child: SizedBox(
            height: 54,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                leading,
                const SizedBox(width: 12),
                Flexible(
                  child: Text(
                    label,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.labelMd.copyWith(color: p.ink, fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// "Sign in as Guest": a tinted full-width button, so it is easy to find.
class _GuestButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  const _GuestButton({required this.label, this.onPressed});

  @override
  Widget build(BuildContext context) {
    final p = OnbPalette.of(context);
    final radius = BorderRadius.circular(16);
    return Opacity(
      opacity: onPressed == null ? 0.6 : 1,
      child: Material(
        color: p.guestFill,
        borderRadius: radius,
        child: InkWell(
          borderRadius: radius,
          onTap: onPressed,
          child: SizedBox(
            height: 52,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.person_outline_rounded, size: 22, color: p.accent),
                const SizedBox(width: 10),
                Flexible(
                  child: Text(
                    label,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.labelMd.copyWith(color: p.accent, fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Google's four-colour "G", painted.
class GoogleG extends StatelessWidget {
  final double size;
  const GoogleG({super.key, this.size = 22});

  @override
  Widget build(BuildContext context) => SizedBox.square(
    dimension: size,
    child: const CustomPaint(painter: _GooglePainter()),
  );
}

class _GooglePainter extends CustomPainter {
  const _GooglePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width;
    final stroke = s * 0.2;
    final c = Offset(s / 2, s / 2);
    final rect = Rect.fromCircle(center: c, radius: s / 2 - stroke / 2);
    Paint arc(Color color) => Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke;
    // Angles run clockwise from 3 o'clock; the G opens at the upper right.
    canvas.drawArc(rect, -0.05, 0.85, false, arc(const Color(0xFF4285F4)));
    canvas.drawArc(rect, 0.8, 1.55, false, arc(const Color(0xFF34A853)));
    canvas.drawArc(rect, 2.35, 1.2, false, arc(const Color(0xFFFBBC05)));
    canvas.drawArc(rect, 3.55, 1.95, false, arc(const Color(0xFFEA4335)));
    canvas.drawRect(
      Rect.fromLTRB(s * 0.5, c.dy - stroke / 2, s - stroke * 0.05, c.dy + stroke / 2),
      Paint()..color = const Color(0xFF4285F4),
    );
  }

  @override
  bool shouldRepaint(_GooglePainter old) => false;
}
