// Field checks shared by the sign-in, reset-password and edit-profile forms
// (mobile/lib/pages/auth_page.dart). Each returns an error message or null.

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Digits only, keeping a leading +; spaces, dashes and brackets dropped. */
export function normalizePhone(raw: string) {
  const trimmed = raw.trim();
  const digits = trimmed.replace(/[^0-9]/g, '');
  return trimmed.startsWith('+') ? `+${digits}` : digits;
}

export function validateEmail(v: string) {
  const s = v.trim();
  if (!s) return 'Enter your email.';
  if (!EMAIL.test(s)) return "That doesn't look like an email address.";
  return null;
}

export function validatePhone(v: string) {
  const s = normalizePhone(v);
  if (!s) return 'Enter your phone number.';
  const digits = s.replace('+', '');
  if (digits.length < 10 || digits.length > 15) {
    return 'Enter a 10-digit mobile number (with country code if outside India).';
  }
  return null;
}

export function validateOccupation(v: string) {
  const s = v.trim();
  if (!s) return 'Enter your occupation.';
  if (s.length > 60) return 'Keep it under 60 characters.';
  return null;
}

export function validateNewPassword(v: string) {
  if (!v) return 'Enter a password.';
  if (v.length < 8) return 'Use at least 8 characters.';
  return null;
}
