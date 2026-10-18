import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import FamilySwitcher from "@/components/FamilySwitcher";
import TermsGate from "@/components/TermsGate";
import OnboardingGate from "@/components/OnboardingGate";
import { SignOut, House, User as UserIcon, TShirt, Sparkle, GearSix, MagnifyingGlass, Crown } from "@phosphor-icons/react";

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  const navItem = ({ isActive }) =>
    `flex items-center gap-2 px-2 py-2 label-caps whitespace-nowrap transition-colors duration-200 ${
      isActive ? "!text-white border-b border-white" : "!text-neutral-400 hover:!text-white"
    }`;

  return (
    <div className="min-h-screen bg-[#FDFDFD]">
      <header className="theme-dark sticky top-0 z-30 border-b hairline">
        <div className="max-w-[1400px] mx-auto px-6 md:px-10 flex items-center justify-between py-4">
          <div
            className="flex items-center gap-2 cursor-pointer shrink-0 mr-6"
            onClick={() => navigate("/dashboard")}
            data-testid="shell-brand"
          >
            <img src="/logo-white.png" alt="MY ATELIER" className="h-8 w-auto" translate="no" />
            <div className="ml-3 relative z-10" onClick={(e) => e.stopPropagation()}>
              <LanguageSwitcher />
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-3 xl:gap-5" translate="no">
            <NavLink to="/dashboard" className={navItem} data-testid="nav-dashboard">
              <House size={14} weight="duotone" /> {t("nav.home")}
            </NavLink>
            <NavLink to="/studio" className={navItem} data-testid="nav-studio">
              <Sparkle size={14} weight="duotone" /> {t("nav.studio")}
            </NavLink>
            <NavLink to="/analyze" className={navItem} data-testid="nav-analyze">
              <MagnifyingGlass size={14} weight="duotone" /> {t("nav.analyze")}
            </NavLink>
            <NavLink to="/wardrobe" className={navItem} data-testid="nav-wardrobe">
              <TShirt size={14} weight="duotone" /> {t("nav.wardrobe")}
            </NavLink>
            <NavLink to="/profile" className={navItem} data-testid="nav-profile">
              <UserIcon size={14} weight="duotone" /> {t("nav.profile")}
            </NavLink>
            <NavLink to="/settings" className={navItem} data-testid="nav-settings">
              <GearSix size={14} weight="duotone" /> {t("nav.settings")}
            </NavLink>
          </nav>
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            {user?.is_owner && (
              <Link to="/stanza" title="Stanza del Proprietario" className="text-[#D4AF37] hover:scale-110 transition-transform" data-testid="owner-crown-btn">
                <Crown size={24} weight="fill" />
              </Link>
            )}
            <FamilySwitcher />
            {user?.picture && (
              <img src={user.picture} alt="" className="hidden sm:block w-8 h-8 object-cover" style={{ borderRadius: 2 }} />
            )}
            <div className="hidden sm:block text-right">
              <div className="text-sm font-medium" data-testid="shell-user-name">{user?.name}</div>
              <div className="text-xs text-neutral-500">{user?.email}</div>
            </div>
            <button data-testid="logout-btn" onClick={logout} className="btn-ghost !px-3 !py-2" title="Logout">
              <SignOut size={16} weight="bold" />
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-[1400px] mx-auto px-6 md:px-10 py-10">{children}</main>
      <TermsGate />
      <OnboardingGate />
      <footer className="border-t hairline mt-16" data-testid="ip-footer">
        <div
          className="max-w-[1400px] mx-auto px-6 md:px-10 py-6 text-center"
          style={{ fontSize: "10px", color: "#9CA3AF", letterSpacing: "0.05em" }}
          translate="no"
        >
          Metodo Fitting Accuracy® — Sistema brevettato per la verifica dell&apos;affidabilità dell&apos;utente — Atelier Fit Proprietary Technology
          <div className="mt-2">
            <Link to="/termini" className="underline hover:text-[#0A0A0A]" data-testid="shell-terms-link">Termini e Condizioni</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
