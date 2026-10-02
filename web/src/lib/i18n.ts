// The app's own text in the app language — the one picked on the Languages
// page before signing in, or later in Settings > Language. Strings are
// written in English in the code and looked up in UI_STRINGS (uiStrings.ts,
// generated from i18n/ui_strings.json, which mobile/ shares); a string with
// no translation shows in English. Weather answers, condition labels and
// warning text come from the backend already in the language.
import { useCallback } from 'react';
import { useUiPrefs, type LangCode } from '../state/UiPrefsContext';
import { UI_STRINGS } from './uiStrings';

export type Args = Record<string, string | number | null | undefined>;

/** `en` in `lang`, with `{name}` placeholders filled from `args`. */
export function translate(lang: LangCode, en: string, args?: Args): string {
  let s = UI_STRINGS[lang]?.[en] ?? en;
  if (args) for (const [k, v] of Object.entries(args)) s = s.split(`{${k}}`).join(v == null ? '' : String(v));
  return s;
}

export type T = (en: string, args?: Args) => string;

/** `t(en, args)` in the app language; re-renders on a language change. */
export function useT(): T {
  const { lang } = useUiPrefs();
  return useCallback((en: string, args?: Args) => translate(lang, en, args), [lang]);
}
