import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import Landing from "@/pages/Landing";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Profile from "@/pages/Profile";
import Studio from "@/pages/Studio";
import Wardrobe from "@/pages/Wardrobe";
import TryOnDetail from "@/pages/TryOnDetail";
import AppShell from "@/components/AppShell";
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
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route path="/profile" element={<Protected><Profile /></Protected>} />
      <Route path="/studio" element={<Protected><Studio /></Protected>} />
      <Route path="/wardrobe" element={<Protected><Wardrobe /></Protected>} />
      <Route path="/tryon/:id" element={<Protected><TryOnDetail /></Protected>} />
    </Routes>
  );
}

export default function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
          <Toaster position="top-center" theme="light" />
        </BrowserRouter>
      </AuthProvider>
    </I18nProvider>
  );
}
