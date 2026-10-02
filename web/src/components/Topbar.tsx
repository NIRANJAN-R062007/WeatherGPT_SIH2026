// The mockups' top bar: menu (phones), the WeatherGPT mark and name, and the
// bell (jumps to Alerts & Warnings). Transparent — it sits on the shell's
// sky. The city pill lives just below it, in each page's scenery header.
import { useNavigate } from 'react-router-dom';
import { BrandTitle } from './Brand';
import { Icon } from './ui';
import { useT } from '../lib/i18n';

export default function Topbar({ onMenu }: { onMenu: () => void }) {
  const t = useT();
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-40 h-14 flex items-center gap-1 px-1 lg:px-space-lg bg-sky-top/80 backdrop-blur-md">
      <button
        type="button"
        onClick={onMenu}
        aria-label={t('Menu')}
        className="lg:hidden p-2.5 rounded-full text-ink hover:bg-ink/5"
      >
        <Icon name="menu" size={24} />
      </button>
      <span className="lg:hidden">
        <BrandTitle />
      </span>
      <span className="flex-1" />
      <button
        type="button"
        onClick={() => navigate('/alerts')}
        aria-label={t('Alerts & Warnings')}
        title={t('Alerts & Warnings')}
        className="p-2.5 rounded-full text-ink hover:bg-ink/5"
      >
        <Icon name="notifications" size={24} />
      </button>
    </header>
  );
}
