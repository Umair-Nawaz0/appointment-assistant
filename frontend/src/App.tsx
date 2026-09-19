import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/AppLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppointmentsPage } from './pages/AppointmentsPage';
import { ForgotPasswordPage, LoginPage, ResetPasswordPage, SignupPage, VerifyEmailPage } from './pages/AuthPages';
import { AvailabilityPage } from './pages/AvailabilityPage';
import { BusinessPage, SettingsPage } from './pages/BusinessPages';
import { ConversationsPage } from './pages/ConversationsPage';
import { CustomersPage } from './pages/CustomersPage';
import { DashboardPage } from './pages/DashboardPage';
import { PatientChatPage } from './pages/PatientChatPage';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<PatientChatPage />} />
      <Route path="/chat" element={<PatientChatPage />} />
      <Route path="/book" element={<PatientChatPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/appointments" element={<AppointmentsPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/conversations" element={<ConversationsPage />} />
        <Route path="/business" element={<BusinessPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/availability" element={<AvailabilityPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
