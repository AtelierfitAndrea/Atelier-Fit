import { useSubscription } from "@/lib/subscription";

export default function IncludedNote({ className = "", light = false, testid = "included-note" }) {
  const { status } = useSubscription();
  if (!status || !(status.honeymoon_active || status.plan === "SINGLE" || status.plan === "FAMILY")) return null;
  return (
    <div className={`text-xs ${light ? "text-white/70" : "text-[#2E7D32]"} ${className}`} translate="no" data-testid={testid}>
      Incluso nel tuo abbonamento Atelier Fit
    </div>
  );
}
