import { Link } from 'react-router-dom';
import { useSettings } from '../state/SettingsContext';
import { useT } from '../i18n/strings';

export function NotFoundPage() {
  const { lang } = useSettings();
  const t = useT(lang);
  return (
    <p className="text-lg text-ink-dim">
      {t.notFound}{' '}
      <Link to="/" className="text-monsoon underline underline-offset-2 hover:text-monsoon-dim">
        {t.navAsk}
      </Link>
    </p>
  );
}
