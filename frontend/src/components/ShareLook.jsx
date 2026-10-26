import { useState } from "react";
import { toast } from "sonner";
import { ShareNetwork, WhatsappLogo, InstagramLogo, FacebookLogo, TelegramLogo } from "@phosphor-icons/react";
import { fileUrl } from "@/lib/api";

const SITE = "https://myatelierapp.it";
const TEXT = `Provalo anche tu su ${SITE}`;
const LINKS = [
  ["whatsapp", "WhatsApp", WhatsappLogo, `https://wa.me/?text=${encodeURIComponent(TEXT)}`],
  ["facebook", "Facebook", FacebookLogo, `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(SITE)}&quote=${encodeURIComponent(TEXT)}`],
  ["telegram", "Telegram", TelegramLogo, `https://t.me/share/url?url=${encodeURIComponent(SITE)}&text=${encodeURIComponent("Provalo anche tu su My Atelier")}`],
];

async function loadFile(path) {
  const res = await fetch(fileUrl(path), { credentials: "include" });
  if (!res.ok) throw new Error("download");
  const blob = await res.blob();
  return new File([blob], `myatelier-look.${blob.type.includes("png") ? "png" : "jpg"}`, { type: blob.type });
}

function download(file) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(file);
  a.download = file.name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

// One tap: phone share sheet (WhatsApp, Instagram, Facebook, Telegram...) with the signed photo + invite; desktop gets direct buttons.
export default function ShareLook({ path, className = "" }) {
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);

  const share = async () => {
    setBusy(true);
    try {
      const file = await loadFile(path);
      if (navigator.canShare?.({ files: [file] })) {
        try { await navigator.share({ files: [file], text: TEXT, title: "My Atelier" }); } catch (e) { if (e?.name !== "AbortError") setMenu(true); }
        return;
      }
      setMenu(true);
    } catch { toast.error("Condivisione non riuscita, riprova"); }
    finally { setBusy(false); }
  };

  const instagram = async () => {
    try {
      download(await loadFile(path));
      await navigator.clipboard?.writeText(TEXT).catch(() => {});
      toast.success("Foto salvata e invito copiato: aprila su Instagram e incolla il testo");
    } catch { toast.error("Salvataggio non riuscito"); }
  };

  return (
    <div className={className} data-testid="share-look">
      <button onClick={share} disabled={busy} data-testid="share-look-btn"
        className="w-full inline-flex items-center justify-center gap-2 border border-[#1A1A1A] bg-white text-[#1A1A1A] px-5 py-3.5 text-xs font-semibold uppercase tracking-[0.18em] hover:bg-[#1A1A1A] hover:text-white disabled:opacity-60 transition-colors duration-300">
        <ShareNetwork size={16} weight="bold" /> {busy ? "Preparo la foto..." : "Condividi il look"}
      </button>
      {menu && (
        <div className="mt-2 grid grid-cols-4 gap-2" data-testid="share-look-menu">
          {LINKS.map(([k, label, Icon, href]) => (
            <a key={k} href={href} target="_blank" rel="noopener noreferrer" data-testid={`share-${k}`}
              className="flex flex-col items-center gap-1 border hairline bg-white py-2.5 text-[11px] hover:border-[#1A1A1A] transition-colors">
              <Icon size={22} weight="duotone" /> {label}
            </a>
          ))}
          <button onClick={instagram} data-testid="share-instagram"
            className="flex flex-col items-center gap-1 border hairline bg-white py-2.5 text-[11px] hover:border-[#1A1A1A] transition-colors">
            <InstagramLogo size={22} weight="duotone" /> Instagram
          </button>
        </div>
      )}
    </div>
  );
}
