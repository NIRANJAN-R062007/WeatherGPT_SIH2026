// Settings — the pics/ mockup (mobile settings_page.dart): the persona
// profile card with "Change Persona", then one row per preference
// (Language, Units, Location, Appearance, About), each opening a picker.
// Language reaches /ask, /facts and /warnings; Persona reaches /ask's
// `persona` param and themes the app; Appearance switches every persona
// between its light and dark palette. The account lives on the Profile
// page. There is no Notifications row: proactive pushes need a push channel
// (POST /alerts/subscribe takes an FCM token or webhook) the site doesn't
// have.
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CityPickerSheet } from '../components/CityPicker';
import PageFrame from '../components/PageFrame';
import { ActionRow, AppCard, IconDisc, OptionTile, PageHeader, Sheet } from '../components/ui';
import { LANG_NAMES, useUiPrefs, type Appearance, type LangCode, type Unit } from '../state/UiPrefsContext';
import { useT } from '../lib/i18n';

const APPEARANCE_LABELS: Record<Appearance, string> = {
  light: 'Light Mode',
  dark: 'Dark Mode',
  system: 'System default',
};

const UNIT_LABELS: Record<Unit, string> = { C: 'Celsius (°C)', F: 'Fahrenheit (°F)' };

type Picker = 'language' | 'units' | 'location' | 'appearance' | 'about' | null;

function Options<T extends string>({
  options,
  selected,
  onPick,
}: {
  options: [T, string][];
  selected: T;
  onPick: (v: T) => void;
}) {
  return (
    <div role="radiogroup" className="flex flex-col gap-space-sm">
      {options.map(([value, label]) => (
        <OptionTile key={value} label={label} selected={value === selected} onClick={() => onPick(value)} />
      ))}
    </div>
  );
}

export default function SettingsPage() {
  const t = useT();
  const prefs = useUiPrefs();
  const navigate = useNavigate();
  const [open, setOpen] = useState<Picker>(null);
  const close = () => setOpen(null);
  const persona = prefs.personaInfo;

  return (
    <PageFrame>
      <PageHeader title="Settings" subtitle="Manage your preferences and experience." />

      <div className="mt-space-lg">
        <AppCard className="!bg-tint !border-tint-strong">
          <div className="flex items-center gap-space-md">
            <IconDisc icon={persona.icon} solid size={52} />
            <div className="min-w-0">
              <div className="font-headline-sm text-headline-sm font-bold text-ink">{t(persona.label)}</div>
              <div className="font-body-sm text-body-sm text-ink-muted">{t(persona.tagline)}</div>
            </div>
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={() => navigate('/persona')}
              className="px-3.5 py-2 rounded-lg bg-card font-label-md text-label-md font-semibold text-primary hover:bg-surface-container-low"
            >
              {t('Change Persona')}
            </button>
          </div>
        </AppCard>
      </div>

      <div className="mt-space-lg flex flex-col gap-space-sm">
        <ActionRow plainIcon icon="language" title="Language" subtitle={LANG_NAMES[prefs.lang]} onClick={() => setOpen('language')} />
        <ActionRow plainIcon icon="device_thermostat" title="Units" subtitle={UNIT_LABELS[prefs.unit]} onClick={() => setOpen('units')} />
        <ActionRow
          plainIcon
          icon="location_on"
          title="Location"
          subtitle={`${t(prefs.cityInfo.name)}, ${t(prefs.cityInfo.region)}`}
          onClick={() => setOpen('location')}
        />
        <ActionRow
          plainIcon
          icon={prefs.isDark ? 'dark_mode' : 'light_mode'}
          title="Appearance"
          subtitle={APPEARANCE_LABELS[prefs.appearance]}
          onClick={() => setOpen('appearance')}
        />
        <ActionRow plainIcon icon="info" title="About" subtitle="WeatherGPT web" onClick={() => setOpen('about')} />
      </div>

      <Sheet
        open={open === 'language'}
        onClose={close}
        title="Language"
        note="Answers, conditions and warning text all follow this language."
      >
        <Options<LangCode>
          options={(Object.keys(LANG_NAMES) as LangCode[]).map((c) => [c, LANG_NAMES[c]])}
          selected={prefs.lang}
          onPick={(v) => {
            prefs.setLang(v);
            close();
          }}
        />
      </Sheet>
      <Sheet
        open={open === 'units'}
        onClose={close}
        title="Units"
        note="Applies to temperatures on Home and Forecast; narrated answers keep the service's units."
      >
        <Options<Unit>
          options={[
            ['C', UNIT_LABELS.C],
            ['F', UNIT_LABELS.F],
          ]}
          selected={prefs.unit}
          onPick={(v) => {
            prefs.setUnit(v);
            close();
          }}
        />
      </Sheet>
      <CityPickerSheet open={open === 'location'} onClose={close} />
      <Sheet
        open={open === 'appearance'}
        onClose={close}
        title="Appearance"
        note="Every persona has a light and a dark look; the persona's colours carry over."
      >
        <Options<Appearance>
          options={(Object.keys(APPEARANCE_LABELS) as Appearance[]).map((a) => [a, APPEARANCE_LABELS[a]])}
          selected={prefs.appearance}
          onPick={(v) => {
            prefs.setAppearance(v);
            close();
          }}
        />
      </Sheet>
      <Sheet open={open === 'about'} onClose={close} title="WeatherGPT">
        <div className="flex items-start gap-3">
          <IconDisc icon="cloud" solid />
          <p className="font-body-md text-body-md text-ink-muted">
            {t(
              'Grounded weather answers in English, हिन्दी, தமிழ், తెలుగు and मराठी. Every number is checked against the source data before you see it.',
            )}
          </p>
        </div>
      </Sheet>
    </PageFrame>
  );
}
