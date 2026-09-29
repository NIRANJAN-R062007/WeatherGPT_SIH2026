// Edit profile, from the Profile page: name, phone and occupation, saved to
// the Supabase account's user_metadata (so they follow the user to any
// device). The email isn't editable here — changing it needs a confirmation
// mail, which the project's default mailer can't deliver yet.
import 'package:flutter/material.dart';

import '../auth_client.dart';
import '../components/common.dart';
import '../components/forms.dart';
import '../components/scenery.dart';
import '../state/auth_store.dart';
import '../theme.dart';
import 'auth_page.dart';

class EditProfilePage extends StatefulWidget {
  final AuthUser user;
  const EditProfilePage({super.key, required this.user});

  @override
  State<EditProfilePage> createState() => _EditProfilePageState();
}

class _EditProfilePageState extends State<EditProfilePage> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.user.fullName);
  late final _phone = TextEditingController(text: widget.user.phone);
  late final _occupation = TextEditingController(text: widget.user.occupation);

  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    for (final c in [_name, _phone, _occupation]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    FocusScope.of(context).unfocus();
    if (!(_form.currentState?.validate() ?? false)) return;
    final auth = AuthStore.read(context);
    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await auth.updateProfile(
        fullName: _name.text,
        phone: normalizePhone(_phone.text),
        occupation: _occupation.text,
      );
      navigator.pop();
      messenger.showSnackBar(const SnackBar(content: Text('Profile saved.')));
    } on AuthError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    const gap = SizedBox(height: 14);
    return SubPageScaffold(
      body: PageFrame(
        showCityPill: false,
        footer: SceneryFooter.soft,
        children: [
          const PageHeader(title: 'Edit profile', subtitle: 'These details appear on your profile on every device.'),
          const SizedBox(height: AppSpace.lg),
          Form(
            key: _form,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                AppTextField(
                  controller: _name,
                  label: 'Full name',
                  icon: Icons.person_outline,
                  capitalization: TextCapitalization.words,
                  autofillHints: const [AutofillHints.name],
                  enabled: !_busy,
                  validator: (v) => (v ?? '').trim().isEmpty ? 'Enter your name.' : null,
                ),
                gap,
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
                gap,
                AppTextField(
                  controller: _occupation,
                  label: 'Occupation',
                  hint: 'e.g. Farmer, Pilot, Student',
                  icon: Icons.work_outline,
                  capitalization: TextCapitalization.sentences,
                  textInputAction: TextInputAction.done,
                  enabled: !_busy,
                  validator: validateOccupation,
                  onSubmitted: (_) => _save(),
                ),
              ],
            ),
          ),
          if (_error != null) ...[const SizedBox(height: AppSpace.md), FormMessage(text: _error!, error: true)],
          const SizedBox(height: AppSpace.lg),
          GradientButton(label: 'Save changes', loading: _busy, onPressed: _save),
        ],
      ),
    );
  }
}
