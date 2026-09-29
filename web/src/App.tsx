import { Navigate, Route, Routes } from 'react-router-dom';
import { BrandMark } from './components/Brand';
import Layout from './components/Layout';
import AlertsPage from './pages/AlertsPage';
import AuthPage from './pages/AuthPage';
import ChatPage from './pages/ChatPage';
import EditProfilePage from './pages/EditProfilePage';
import ForecastPage from './pages/ForecastPage';
import HistoryPage from './pages/HistoryPage';
import HomePage from './pages/HomePage';
import LandingPage from './pages/LandingPage';
import PersonaPage from './pages/PersonaPage';
import ProfilePage from './pages/ProfilePage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import SettingsPage from './pages/SettingsPage';
import { AuthProvider, useAuth } from './state/AuthContext';
import { ChatProvider } from './state/ChatContext';
import { UiPrefsProvider } from './state/UiPrefsContext';
import { WeatherProvider } from './state/WeatherContext';

/** Signed out → the landing page (sign in / create account / guest);
 *  signed in or guest → the app. Signing out (or leaving guest mode) from
 *  Profile lands back on the landing page. */
function Gate() {
  const { status } = useAuth();

  if (status === 'restoring') {
    // The moment between load and the saved session being read.
    return (
      <div className="min-h-screen flex items-center justify-center bg-sky-gradient">
        <BrandMark size={72} />
      </div>
    );
  }

  if (status === 'signedOut') {
    return (
      <Routes>
        <Route index element={<LandingPage />} />
        <Route path="signin" element={<AuthPage initialMode="signIn" />} />
        <Route path="signup" element={<AuthPage initialMode="signUp" />} />
        <Route path="reset-password" element={<ResetPasswordPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }

  return (
    <WeatherProvider>
      <ChatProvider>
        <Routes>
          {/* A guest can still sign in or create an account. */}
          <Route path="signin" element={status === 'guest' ? <AuthPage initialMode="signIn" /> : <Navigate to="/" replace />} />
          <Route path="signup" element={status === 'guest' ? <AuthPage initialMode="signUp" /> : <Navigate to="/" replace />} />
          <Route path="reset-password" element={status === 'guest' ? <ResetPasswordPage /> : <Navigate to="/" replace />} />
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="forecast" element={<ForecastPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="persona" element={<PersonaPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="profile/edit" element={<EditProfilePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ChatProvider>
    </WeatherProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <UiPrefsProvider>
        <Gate />
      </UiPrefsProvider>
    </AuthProvider>
  );
}
