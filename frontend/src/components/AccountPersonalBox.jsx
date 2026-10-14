import { UserCircle, LockKey } from "@phosphor-icons/react";

export default function AccountPersonalBox({ testid = "account-personal-box" }) {
  return (
    <div
      className="flex items-start gap-4 border border-[#A5D6A7] bg-[#E8F5E9] px-5 py-4 text-[#1B5E20]"
      translate="no"
      data-testid={testid}
    >
      <span className="relative shrink-0 mt-0.5" aria-hidden="true">
        <UserCircle size={26} weight="duotone" />
        <LockKey size={13} weight="fill" className="absolute -bottom-1 -right-1 bg-[#E8F5E9] rounded-full" />
      </span>
      <div>
        <div className="font-semibold">Account personale e non cedibile.</div>
        <p className="mt-1 text-sm md:text-base leading-relaxed">
          Il tuo Atelier è cucito su di te. Le tue foto, le tue misure, i tuoi capi sono solo tuoi. L&apos;account è personale e non può essere condiviso o ceduto. Solo tu puoi usarlo.
        </p>
        <p className="mt-2 text-xs md:text-sm text-[#2E7D32]" data-testid={`${testid}-reason`}>
          Non è per bloccarti, è per proteggere la tua vestibilità. Se presti l&apos;account, il nostro sarto digitale sbaglia tutto.
        </p>
      </div>
    </div>
  );
}
