import { Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { UiPrefsProvider } from './state/UiPrefsContext';
import HomePage from './pages/HomePage';
import ChatPage from './pages/ChatPage';
import ForecastPage from './pages/ForecastPage';
import AlertsPage from './pages/AlertsPage';
import HistoryPage from './pages/HistoryPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <UiPrefsProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="forecast" element={<ForecastPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </UiPrefsProvider>
  );
}
