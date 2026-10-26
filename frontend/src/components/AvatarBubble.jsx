import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "@phosphor-icons/react";
import { fileUrl } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";
import AvatarBox from "@/components/AvatarBox";

// Small round profile photo (WhatsApp style); tap opens the photo full screen to change it.
export default function AvatarBubble() {
  const { avatar } = useAvatar();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener("atelier-open-avatar", onOpen);
    return () => window.removeEventListener("atelier-open-avatar", onOpen);
  }, []);
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    if (open) window.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = ""; window.removeEventListener("keydown", onKey); };
  }, [open]);

  return (
    <>
      {avatar?.path && (
        <button onClick={() => setOpen(true)} title="La tua foto" data-testid="avatar-bubble"
          className="w-9 h-9 rounded-full overflow-hidden ring-2 ring-white/70 hover:ring-[#D4AF37] transition-shadow duration-200 shrink-0">
          <img src={`${fileUrl(avatar.path)}?thumb=128`} alt="La tua foto" className="w-full h-full object-cover object-top" />
        </button>
      )}
      {open && createPortal(
        <div className="fixed inset-0 z-[70] bg-[#F5F2EC] overflow-y-auto text-[#0A0A0A]" data-testid="avatar-fullscreen">
          <div className="max-w-3xl mx-auto px-4 py-6 md:py-10">
            <div className="flex justify-end mb-4">
              <button onClick={() => setOpen(false)} className="p-2 border hairline bg-white hover:bg-neutral-100" aria-label="Chiudi" data-testid="avatar-fullscreen-close">
                <X size={20} weight="bold" />
              </button>
            </div>
            <AvatarBox title="Vuoi cambiare foto?" onSaved={() => setOpen(false)} />
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
