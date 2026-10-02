// Persona selection — the pics/ persona mockups (mobile persona_page.dart):
// one illustrated card per persona (its own palette and painted scene, icon
// disc, name, tagline, four focus chips). Opened from Settings' "Change
// Persona", Home's avatar and Profile. Picking a card sets the persona,
// which is both /ask's `persona` param and the app-wide theme: the whole
// app (this page included) cross-fades to that persona's palette, then the
// page returns to where it was opened from.
import { useNavigate } from 'react-router-dom';
import PageFrame from '../components/PageFrame';
import { PersonaScenery } from '../components/scenery/Scenery';
import { AppCard, Icon, IconDisc, PageHeader, SectionTitle } from '../components/ui';
import { PERSONAS, type Persona } from '../data/personas';
import { useUiPrefs } from '../state/UiPrefsContext';
import { alpha, mix, personaThemeFor } from '../theme/personaTheme';
import { useT } from '../lib/i18n';

/** One persona, drawn in its own theme whatever the active persona is. */
function PersonaCard({ persona: p, selected, onPick }: { persona: Persona; selected: boolean; onPick: () => void }) {
  const tr = useT();
  const { isDark } = useUiPrefs();
  const t = personaThemeFor(p.id, isDark ? 'dark' : 'light');
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onPick}
      className="block w-full text-left rounded-[20px] overflow-hidden transition hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2"
      style={{
        background: t.card,
        border: `${selected ? 2 : 1}px solid ${selected ? t.primary : alpha(t.primary, 0.3)}`,
        boxShadow: `0 4px ${selected ? 18 : 12}px ${alpha(t.shadow, selected ? 0.22 : 0.08)}`,
        outlineColor: t.primary,
      }}
    >
      <div
        className="relative min-h-[118px]"
        style={{ background: `linear-gradient(to bottom right, ${t.card} 20%, ${t.skyBottom} 60%, ${t.skyTop})` }}
      >
        <div
          className="absolute right-0 top-0 bottom-0 w-[190px]"
          style={{
            maskImage: 'linear-gradient(to right, transparent, black 45%)',
            WebkitMaskImage: 'linear-gradient(to right, transparent, black 45%)',
          }}
        >
          <PersonaScenery slot="card" theme={t} />
        </div>
        <div className="relative flex items-start gap-3 p-space-md pr-[120px]">
          <span
            className="w-12 h-12 shrink-0 rounded-full flex items-center justify-center"
            style={{ background: `linear-gradient(to bottom right, ${t.primary}, ${mix(t.primary, t.primaryContainer, 0.55)})`, color: t.onPrimary }}
          >
            <Icon name={p.icon} size={26} fill />
          </span>
          <span className="min-w-0">
            <span className="block font-headline-md text-headline-md font-bold" style={{ color: t.ink }}>
              {tr(p.label)}
            </span>
            <span className="block mt-0.5 font-body-sm text-body-sm" style={{ color: t.inkMuted }}>
              {tr(p.tagline)}
            </span>
          </span>
        </div>
        <span className="absolute top-2.5 right-2.5 rounded-full leading-none" style={{ background: t.card }}>
          <Icon
            name={selected ? 'check_circle' : 'radio_button_unchecked'}
            fill={selected}
            size={22}
            style={{ color: selected ? t.primary : t.outline }}
          />
        </span>
      </div>
      <div className="grid grid-cols-2 gap-space-sm px-3 pt-2.5 pb-3">
        {p.features.map((f) => (
          <span
            key={f.label}
            className="flex items-center gap-2 px-2.5 py-2 rounded-xl font-body-sm text-body-sm leading-tight"
            style={{ background: t.tint, color: t.ink }}
          >
            <Icon name={f.icon} size={18} style={{ color: t.primary }} />
            {tr(f.label)}
          </span>
        ))}
      </div>
    </button>
  );
}

/** "You're viewing the app as …" plus what that persona frames. */
function YourPersona({ persona }: { persona: Persona }) {
  const tr = useT();
  return (
    <AppCard wash>
      <div className="flex items-start gap-3">
        <IconDisc icon="verified_user" size={40} className="!bg-card" />
        <p className="font-body-md text-body-md text-ink-muted">
          {tr("You're viewing the app as")}
          <br />
          <span className="font-headline-sm text-headline-sm font-bold text-ink">{tr(persona.label)}</span>
        </p>
      </div>
      <div className="mt-3 font-label-md text-label-md font-bold text-ink">{tr('What you get')}</div>
      <ul className="mt-1.5 flex flex-col gap-1">
        {persona.features.map((f) => (
          <li key={f.label} className="flex items-center gap-2 font-body-md text-body-md text-ink">
            <Icon name="check" size={18} className="text-primary" />
            {tr(f.label)}
          </li>
        ))}
      </ul>
    </AppCard>
  );
}

export default function PersonaPage() {
  const { persona, setPersona, personaInfo } = useUiPrefs();
  const navigate = useNavigate();
  return (
    <PageFrame footer="soft" wide>
      <PageHeader
        title="Choose your persona"
        subtitle="Same trusted numbers, framed the way that's most useful for your role. The whole app takes on the persona you pick."
      />
      <div className="mt-space-lg">
        <YourPersona persona={personaInfo} />
        <div className="mt-space-lg">
          <div className="mb-space-sm">
            <SectionTitle text="All personas" />
          </div>
          <div role="radiogroup" aria-label="Personas" className="grid gap-space-md md:grid-cols-2 xl:grid-cols-3">
            {PERSONAS.map((p) => (
              <PersonaCard
                key={p.id}
                persona={p}
                selected={p.id === persona}
                onPick={() => {
                  setPersona(p.id);
                  // Let the app-wide re-theme show before going back (or
                  // Home, when this page was opened directly).
                  const canGoBack = (window.history.state as { idx?: number } | null)?.idx;
                  window.setTimeout(() => (canGoBack ? navigate(-1) : navigate('/')), 320);
                }}
              />
            ))}
          </div>
        </div>
      </div>
    </PageFrame>
  );
}
