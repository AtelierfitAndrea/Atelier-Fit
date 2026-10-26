import { useState } from "react";
import { toast } from "sonner";
import { DownloadSimple } from "@phosphor-icons/react";
import { fileUrl } from "@/lib/api";

// Downloads the signed photo; on phones opens the share sheet so it can go straight to the photo gallery.
export default function SaveToGallery({ path, className = "", testid = "save-to-gallery-btn" }) {
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      const res = await fetch(fileUrl(path), { credentials: "include" });
      if (!res.ok) throw new Error("download");
      const blob = await res.blob();
      const ext = blob.type.includes("png") ? "png" : "jpg";
      const file = new File([blob], `myatelier-${Date.now()}.${ext}`, { type: blob.type });
      const mobile = window.matchMedia("(pointer: coarse)").matches;
      if (mobile && navigator.canShare?.({ files: [file] })) {
        try { await navigator.share({ files: [file] }); return; } catch (e) { if (e?.name === "AbortError") return; }
      }
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = file.name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast.success("Foto salvata");
    } catch { toast.error("Salvataggio non riuscito, riprova"); }
    finally { setBusy(false); }
  };
  return (
    <button onClick={save} disabled={busy} data-testid={testid}
      className={`w-full inline-flex items-center justify-center gap-2 bg-[#1A1A1A] text-white px-5 py-3.5 label-caps hover:bg-[#8C7355] disabled:opacity-60 transition-colors duration-300 ${className}`}>
      <DownloadSimple size={16} weight="bold" /> {busy ? "Salvataggio..." : "Salva in Galleria"}
    </button>
  );
}
