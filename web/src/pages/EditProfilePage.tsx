// Edit profile, from the Profile page (mobile edit_profile_page.dart): name,
// phone and occupation, saved to the Supabase account's user_metadata so they
// follow the user to any device. The email isn't editable here — changing it
// needs a confirmation mail, which the project's default mailer can't
// deliver yet.
import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { FormMessage, GradientButton, OutlineButton, TextField } from '../components/forms';
import PageFrame from '../components/PageFrame';
import { PageHeader } from '../components/ui';
import { AuthError, type AuthUser } from '../lib/auth';
import { normalizePhone, validateOccupation, validatePhone } from '../lib/validate';
import { useAuth } from '../state/AuthContext';

function EditForm({ user }: { user: AuthUser }) {
  const { updateProfile } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState(user.fullName);
  const [phone, setPhone] = useState(user.phone);
  const [occupation, setOccupation] = useState(user.occupation);
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = {
    name: name.trim() ? null : 'Enter your name.',
    phone: validatePhone(phone),
    occupation: validateOccupation(occupation),
  };
  const shown = (f: keyof typeof errors) => (submitted && errors[f]) || null;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    if (errors.name || errors.phone || errors.occupation) return;
    setBusy(true);
    setError(null);
    try {
      await updateProfile({ fullName: name, phone: normalizePhone(phone), occupation });
      navigate('/profile', { replace: true, state: { saved: true } });
    } catch (err) {
      setError(err instanceof AuthError ? err.message : 'Something went wrong. Please try again.');
      setBusy(false);
    }
  };

  return (
    <form noValidate onSubmit={save} className="mt-space-lg flex flex-col gap-3.5">
      <TextField
        label="Full name"
        icon="person"
        name="name"
        autoComplete="name"
        value={name}
        disabled={busy}
        error={shown('name')}
        onChange={(e) => setName(e.target.value)}
      />
      <TextField
        label="Phone number"
        icon="phone"
        name="phone"
        type="tel"
        autoComplete="tel"
        hint="98765 43210"
        value={phone}
        disabled={busy}
        error={shown('phone')}
        onChange={(e) => setPhone(e.target.value)}
      />
      <TextField
        label="Occupation"
        icon="work"
        name="occupation"
        hint="e.g. Farmer, Pilot, Student"
        value={occupation}
        disabled={busy}
        error={shown('occupation')}
        onChange={(e) => setOccupation(e.target.value)}
      />
      {error && <FormMessage text={error} error />}
      <div className="mt-2 flex flex-col gap-3">
        <GradientButton type="submit" label="Save changes" loading={busy} />
        <OutlineButton label="Cancel" disabled={busy} onClick={() => navigate('/profile')} />
      </div>
    </form>
  );
}

export default function EditProfilePage() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/profile" replace />;
  return (
    <PageFrame showCityPill={false}>
      <div className="max-w-md">
        <PageHeader title="Edit profile" subtitle="These details appear on your profile on every device." />
        <EditForm user={user} />
      </div>
    </PageFrame>
  );
}
