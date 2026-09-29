// Landing — what a signed-out visitor sees first (mobile landing_page.dart):
// the WeatherGPT mark over the persona's painted scene, what the app does,
// and the ways in (create an account / sign in / continue as a guest).
// App.tsx shows it whenever the account is signed out, so signing out lands
// back here.
import { useNavigate } from 'react-router-dom';
import { BrandMark } from '../components/Brand';
import { GradientButton, GuestButton, OutlineButton } from '../components/forms';
import { PersonaScenery } from '../components/scenery/Scenery';
import { Icon } from '../components/ui';

const FEATURES: [string, string, string][] = [
  ['sunny', 'Live forecast', 'Today, tonight and tomorrow for your city.'],
  ['fact_check', 'Answers with evidence', 'Every number is checked against the source data.'],
  ['warning', 'IMD warnings', 'The colour-coded warning, verbatim — never re-graded.'],
  ['translate', 'Five languages', 'English, हिन्दी, தமிழ், తెలుగు, मराठी.'],
];

export default function LandingPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex flex-col bg-sky-gradient">
      <div className="px-space-lg pt-space-lg flex items-center gap-2.5 max-w-5xl w-full mx-auto">
        <BrandMark size={40} />
        <span className="font-headline-lg text-headline-lg-mobile font-extrabold text-ink">WeatherGPT</span>
      </div>
      <div className="relative h-[150px] shrink-0">
        <PersonaScenery slot="header" />
      </div>
      <main className="flex-1 bg-sheet rounded-t-sheet shadow-[0_-2px_16px_rgb(var(--c-shadow)/0.06)]">
        <div className="mx-auto max-w-5xl px-space-lg pt-7 pb-space-xl grid gap-space-xl md:grid-cols-2 md:items-center">
          <div>
            <h1 className="font-headline-xl text-[32px] md:text-headline-xl leading-[1.15] font-bold text-ink">
              Weather answers
              <br />
              you can trust.
            </h1>
            <p className="mt-space-sm font-body-md text-body-md md:text-body-lg text-ink-muted">
              Ask about rain, heat or wind for your city and get a plain answer — grounded in live data, framed for
              how you work.
            </p>
            <ul className="mt-space-lg flex flex-col gap-3">
              {FEATURES.map(([icon, title, body]) => (
                <li key={title} className="flex items-start gap-3">
                  <span className="w-10 h-10 shrink-0 rounded-xl bg-tint text-primary flex items-center justify-center">
                    <Icon name={icon} size={21} />
                  </span>
                  <span>
                    <span className="block font-label-md text-[14px] font-bold text-ink">{title}</span>
                    <span className="block font-body-sm text-body-sm text-ink-muted">{body}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex flex-col gap-3 md:max-w-sm md:justify-self-end md:w-full">
            <GradientButton label="Create account" icon="arrow_forward" onClick={() => navigate('/signup')} />
            <OutlineButton label="I already have an account" onClick={() => navigate('/signin')} />
            <GuestButton />
          </div>
        </div>
      </main>
    </div>
  );
}
