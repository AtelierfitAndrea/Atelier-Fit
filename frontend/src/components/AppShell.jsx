import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { SignOut, House, User as UserIcon, TShirt, Sparkle } from "@phosphor-icons/react";

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  const navItem = ({ isActive }) =>
    `flex items-center gap-2 px-3 py-2 label-caps transition-colors duration-200 ${
      isActive ? "text-[#0A0A0A] border-b border-[#0A0A0A]" : "text-neutral-500 hover:text-[#0A0A0A]"
    }`;

  return (
    <div className="min-h-screen bg-[#FDFDFD]">
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-xl border-b hairline">
        <div className="max-w-[1400px] mx-auto px-6 md:px-10 flex items-center justify-between py-4">
          <div
            className="flex items-center gap-2 cursor-pointer"
            onClick={() => navigate("/dashboard")}
            data-testid="shell-brand"
          >
            <div className="w-5 h-5 bg-[#0A0A0A]" />
            <span className="font-serif text-lg tracking-tight" translate="no">Atelier Fit</span>
            <div className="ml-3">
              <LanguageSwitcher />
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-6" translate="no">
            <NavLink to="/dashboard" className={navItem} data-testid="nav-dashboard">
              <House size={14} weight="duotone" /> {t("nav.home")}
            </NavLink>
            <NavLink to="/studio" className={navItem} data-testid="nav-studio">
              <Sparkle size={14} weight="duotone" /> {t("nav.studio")}
            </NavLink>
            <NavLink to="/wardrobe" className={navItem} data-testid="nav-wardrobe">
              <TShirt size={14} weight="duotone" /> {t("nav.wardrobe")}
            </NavLink>
            <NavLink to="/profile" className={navItem} data-testid="nav-profile">
              <UserIcon size={14} weight="duotone" /> {t("nav.profile")}
            </NavLink>
          </nav>
          <div className="flex items-center gap-4">
            {user?.picture && (
              <img src={user.picture} alt="" className="w-8 h-8 object-cover" style={{ borderRadius: 2 }} />
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
    </div>
  );
}
