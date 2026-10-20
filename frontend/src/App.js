import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import { SubscriptionProvider } from "@/lib/subscription";
import { AvatarProvider } from "@/lib/avatar";
import PaywallModal from "@/components/PaywallModal";
import Landing from "@/pages/Landing";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Profile from "@/pages/Profile";
import Studio from "@/pages/Studio";
import Wardrobe from "@/pages/Wardrobe";
import TryOnDetail from "@/pages/TryOnDetail";
import Settings from "@/pages/Settings";
import AnalyzeProduct from "@/pages/AnalyzeProduct";
import AppShell from "@/components/AppShell";
import Terms from "@/pages/Terms";
import ComingSoon, { LAUNCH_AT } from "@/components/ComingSoon";
import AdminAtelier from "@/pages/AdminAtelier";
import AdminSupport from "@/pages/AdminSupport";
import Support from "@/pages/Support";
import PaymentResult from "@/pages/PaymentResult";
import SessionRevokedNotice from "@/components/SessionRevokedNotice";
import "@/App.css";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-xs tracking-[0.3em] uppercase text-neutral-500">Loading</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/" replace />;
  return <AppShell>{children}</AppShell>;
}

function AppRouter() {
  const location = useLocation();
  const { user, loading } = useAuth();
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  if (loading) {
    return (
      <div style={{ backgroundColor: "#000", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", letterSpacing: "0.5em", fontSize: "14px", fontWeight: 300 }} data-testid="gate-loading">
        MY ATELIER
      </div>
    );
  }
  if (!user && location.pathname !== "/termini" && Date.now() < LAUNCH_AT) return <ComingSoon />;
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/termini" element={<Terms />} />
      <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route path="/profile" element={<Protected><Profile /></Protected>} />
      <Route path="/studio" element={<Protected><Studio /></Protected>} />
      <Route path="/wardrobe" element={<Protected><Wardrobe /></Protected>} />
      <Route path="/tryon/:id" element={<Protected><TryOnDetail /></Protected>} />
      <Route path="/settings" element={<Protected><Settings /></Protected>} />
      <Route path="/analyze" element={<Protected><AnalyzeProduct /></Protected>} />
      <Route path="/stanza" element={user?.is_owner ? <AdminAtelier /> : <Navigate to="/dashboard" replace />} />
      <Route path="/stanza/assistenza" element={user?.is_owner ? <AdminSupport /> : <Navigate to="/dashboard" replace />} />
      <Route path="/assistenza" element={<Protected><Support /></Protected>} />
      <Route path="/payment/success" element={<Protected><PaymentResult /></Protected>} />
      <Route path="/payment/cancel" element={<Protected><PaymentResult /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <SubscriptionProvider>
          <AvatarProvider>
          <BrowserRouter>
            <AppRouter />
            <PaywallModal />
            <Toaster position="top-center" theme="light" />
            <SessionRevokedNotice />
          </BrowserRouter>
          </AvatarProvider>
        </SubscriptionProvider>
      </AuthProvider>
    </I18nProvider>
  );
}
