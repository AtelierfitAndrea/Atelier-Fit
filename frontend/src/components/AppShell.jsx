import { Link, NavLink, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import FamilySwitcher from "@/components/FamilySwitcher";
import TermsGate from "@/components/TermsGate";
import OnboardingGate from "@/components/OnboardingGate";
import ReminderPopup from "@/components/ReminderPopup";
import AvatarBubble from "@/components/AvatarBubble";
import BookButton, { BookAsk } from "@/components/PoseBook";
import { SignOut, House, User as UserIcon, TShirt, Sparkle, GearSix, MagnifyingGlass, Crown, Question } from "@phosphor-icons/react";

function useSupportPending() {
  const { user } = useAuth();
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!user?.is_owner) return undefined;
    const load = () => api.get("/admin/support/pending-count").then(({ data }) => setN(data.pending)).catch(() => {});
    load();
    const id = setInterval(load, 60000);
    window.addEventListener("atelier-support-changed", load);
    return () => { clearInterval(id); window.removeEventListener("atelier-support-changed", load); };
  }, [user?.is_owner]);
  return n;
}

export default function AppShell({ children }) {
  const pending = useSupportPending();
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
        <div className="max-w-[1400px] mx-auto px-3 sm:px-6 md:px-10 flex items-center justify-between gap-2 py-4">
          <div
            className="flex items-center gap-2 cursor-pointer shrink-0 mr-0 sm:mr-6"
            onClick={() => navigate("/dashboard")}
            data-testid="shell-brand"
          >
            <img src="/logo-white.png" alt="MY ATELIER" className="h-7 sm:h-8 w-auto" translate="no" />
            <div className="ml-1.5 sm:ml-3 relative z-10" onClick={(e) => e.stopPropagation()}>
              <LanguageSwitcher />
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-3 xl:gap-5" translate="no">
            <NavLink to="/dashboard" className={navItem} data-testid="nav-dashboard">
              <House size={14} weight="duotone" /> <span className="hidden min-[1680px]:inline">{t("nav.home")}</span>
            </NavLink>
            <NavLink to="/studio" className={navItem} data-testid="nav-studio">
              <Sparkle size={14} weight="duotone" /> <span className="hidden min-[1680px]:inline">{t("nav.studio")}</span>
            </NavLink>
            <NavLink to="/analyze" className={navItem} data-testid="nav-analyze">
              <MagnifyingGlass size={14} weight="duotone" /> <span className="hidden min-[1680px]:inline">{t("nav.analyze")}</span>
            </NavLink>
            <NavLink to="/wardrobe" className={navItem} data-testid="nav-wardrobe">
              <TShirt size={14} weight="duotone" /> <span className="hidden min-[1680px]:inline">{t("nav.wardrobe")}</span>
            </NavLink>
            <NavLink to="/profile" className={navItem} data-testid="nav-profile">
              <UserIcon size={14} weight="duotone" /> <span className="hidden min-[1680px]:inline">{t("nav.profile")}</span>
            </NavLink>
            <NavLink to="/settings" className={navItem} data-testid="nav-settings">
              <GearSix size={14} weight="duotone" /> <span className="hidden min-[1680px]:inline">{t("nav.settings")}</span>
            </NavLink>
            <NavLink to="/assistenza" className={navItem} data-testid="nav-support">
              <Question size={14} weight="duotone" /> <span className="hidden min-[1680px]:inline">{t("nav.support")}</span>
            </NavLink>
          </nav>
          <div className="flex items-center gap-1.5 sm:gap-4 min-w-0">
            {user?.is_owner && (
              <Link to={pending ? "/stanza/assistenza" : "/stanza"} title={pending ? `${pending} conversazioni da gestire` : "Stanza del Proprietario"} className="relative text-[#D4AF37] hover:scale-110 transition-transform" data-testid="owner-crown-btn">
                <Crown size={24} weight="fill" />
                {pending > 0 && (
                  <span className="absolute -top-2 -right-2.5 min-w-[17px] h-[17px] px-1 rounded-full bg-[#D4AF37] text-[#0A0A0A] text-[10px] font-semibold leading-[17px] text-center ring-2 ring-[#0A0A0A]" data-testid="owner-crown-pending">{pending > 99 ? "99+" : pending}</span>
                )}
              </Link>
            )}
            <Link to="/assistenza" className="md:hidden" title="Assistenza" data-testid="nav-support-mobile"><Question size={22} weight="duotone" /></Link>
            <FamilySwitcher />
            <BookButton />
            <AvatarBubble />
            <button data-testid="logout-btn" onClick={logout} className="btn-ghost !px-3 !py-2" title="Logout">
              <SignOut size={16} weight="bold" />
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-[1400px] mx-auto px-6 md:px-10 py-10">{children}</main>
      <BookAsk />
      <TermsGate />
      <OnboardingGate />
      <ReminderPopup />
      <footer className="border-t hairline mt-16" data-testid="ip-footer">
        <div
          className="max-w-[1400px] mx-auto px-6 md:px-10 py-6 text-center"
          style={{ fontSize: "10px", color: "#9CA3AF", letterSpacing: "0.05em" }}
          translate="no"
        >
          Atelier Fit Proprietary Technology
          <div className="mt-2">
            <Link to="/termini" className="underline hover:text-[#0A0A0A]" data-testid="shell-terms-link">Termini e Condizioni</Link>
            <span className="mx-2">·</span>
            <Link to="/assistenza" className="underline hover:text-[#0A0A0A]" data-testid="shell-support-link">Assistenza</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
