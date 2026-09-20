import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AskPage } from './pages/AskPage';
import { DashboardPage } from './pages/DashboardPage';
import { WarningsPage } from './pages/WarningsPage';
import { SettingsPage } from './pages/SettingsPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { CitiesProvider } from './state/CitiesContext';
import { SettingsProvider } from './state/SettingsContext';
import { useSmoothScroll } from './hooks/useSmoothScroll';

export default function App() {
  useSmoothScroll();

  return (
    <SettingsProvider>
      <CitiesProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<AskPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/warnings" element={<WarningsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Layout>
      </CitiesProvider>
    </SettingsProvider>
  );
}
