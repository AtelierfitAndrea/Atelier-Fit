import { LockKey } from "@phosphor-icons/react";

export default function PrivacyBox({ testid }) {
  return (
    <div
      className="flex items-start gap-4 border border-[#A5D6A7] bg-[#E8F5E9] px-5 py-4 text-[#1B5E20]"
      translate="no"
      data-testid={testid}
    >
      <LockKey size={26} weight="duotone" className="shrink-0 mt-0.5" aria-hidden="true" />
      <p className="text-sm md:text-base leading-relaxed">
        Le tue foto sono solo tue. Sempre. Le usiamo solo per mostrarti come ti starebbero i vestiti. Sono protette, visibili solo a te, non le vendiamo e non le cediamo a nessuno. Puoi cancellarle quando vuoi.
      </p>
    </div>
  );
}
