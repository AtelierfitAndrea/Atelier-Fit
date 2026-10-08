import { useEffect, useRef, useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import { LANGS, useI18n } from "@/lib/i18n";

export default function LanguageSwitcher() {
  const { lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const active = LANGS.find((l) => l.code === lang) || LANGS[0];

  return (
    <div className="relative" ref={ref} data-testid="lang-switcher">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 border hairline bg-white px-3 py-2 label-caps hover:border-[#0A0A0A] transition-colors"
        data-testid="lang-switcher-trigger"
        translate="no"
      >
        <span className="text-base leading-none" aria-hidden>{active.flag}</span>
        <span>{active.label}</span>
        <CaretDown size={10} weight="bold" className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-2 z-40 min-w-[128px] bg-white border hairline shadow-lg"
          data-testid="lang-switcher-menu"
        >
          {LANGS.map((l) => (
            <button
              key={l.code}
              onClick={() => { setLang(l.code); setOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2 label-caps transition-colors ${
                l.code === lang ? "bg-[#0A0A0A] text-white" : "hover:bg-neutral-50"
              }`}
              data-testid={`lang-option-${l.code}`}
              translate="no"
            >
              <span className="text-base leading-none" aria-hidden>{l.flag}</span>
              <span>{l.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
