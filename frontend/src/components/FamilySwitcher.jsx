import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { UsersThree, Check, Plus, PencilSimple } from "@phosphor-icons/react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api, getActiveProfile, setActiveProfile } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useSubscription } from "@/lib/subscription";

function NameForm({ initial = "", onSubmit, testid, label }) {
  const { t } = useI18n();
  const [name, setName] = useState(initial);
  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim()); }}
    >
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={40}
        placeholder={t("family.placeholder")}
        className="flex-1 border hairline px-3 py-2 text-sm outline-none focus:border-[#0A0A0A]"
        data-testid={`${testid}-input`}
      />
      <button type="submit" className="bg-[#0A0A0A] text-white px-3 py-2 label-caps" data-testid={`${testid}-submit`}>
        {label}
      </button>
    </form>
  );
}

export default function FamilySwitcher() {
  const { t } = useI18n();
  const { status } = useSubscription();
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);
  const isFamily = status?.plan === "FAMILY";

  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/family/profiles"); setData(d); } catch (_e) { /* ignore */ }
  }, []);

  useEffect(() => {
    if (!status) return;
    if (!isFamily) {
      if (getActiveProfile()) { setActiveProfile(null); window.location.reload(); }
      return;
    }
    load();
  }, [status, isFamily, load]);

  if (!isFamily || !data) return null;

  const owner = data.profiles[0];
  const activeId = getActiveProfile() || owner.profile_id;
  const active = data.profiles.find((p) => p.profile_id === activeId) || owner;

  const switchTo = (p) => {
    if (p.profile_id === active.profile_id) return;
    setActiveProfile(p.is_owner ? null : p.profile_id);
    window.location.reload();
  };

  const save = async (fn) => {
    try { const { data: d } = await fn(); setData(d); setEditing(null); }
    catch (e) { toast.error(e?.response?.data?.detail || "Error"); }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="flex items-center gap-2 border hairline px-3 py-2 label-caps hover:border-[#0A0A0A] transition-colors" data-testid="family-switcher-btn" translate="no">
          <UsersThree size={14} weight="duotone" />
          <span className="max-w-[110px] truncate" data-testid="family-active-name">{active.name}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 rounded-none p-0" translate="no" data-testid="family-switcher-panel">
        <div className="p-4 border-b hairline">
          <div className="label-caps">{t("family.title")}</div>
          <p className="text-xs text-neutral-500 mt-1">{t("family.private")}</p>
        </div>
        <ul>
          {data.profiles.map((p, i) => (
            <li key={p.profile_id} className="border-b hairline">
              {editing === p.profile_id ? (
                <div className="p-3">
                  <NameForm initial={p.name} label={t("family.save")} testid={`family-rename-${i}`}
                    onSubmit={(name) => save(() => api.patch(`/family/profiles/${p.profile_id}`, { name }))} />
                </div>
              ) : (
                <div className="flex items-center">
                  <button onClick={() => switchTo(p)} className="flex-1 flex items-center gap-3 px-4 py-3 text-left hover:bg-neutral-50" data-testid={`family-profile-${i}`}>
                    <span className="w-4">{p.profile_id === active.profile_id && <Check size={14} weight="bold" />}</span>
                    <span className="text-sm">{p.name}</span>
                    {p.is_owner && <span className="label-caps text-neutral-400 ml-auto">{t("family.owner")}</span>}
                  </button>
                  {!p.is_owner && (
                    <button onClick={() => setEditing(p.profile_id)} className="px-3 text-neutral-400 hover:text-[#0A0A0A]" title={t("family.rename")} data-testid={`family-rename-btn-${i}`}>
                      <PencilSimple size={14} />
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
        <div className="p-4">
          {data.profiles.length < data.max_profiles ? (
            <>
              <div className="label-caps mb-2 flex items-center gap-1"><Plus size={12} /> {t("family.add")} ({data.profiles.length}/{data.max_profiles})</div>
              <NameForm key={data.profiles.length} label={t("family.save")} testid="family-add"
                onSubmit={(name) => save(() => api.post("/family/profiles", { name }))} />
            </>
          ) : (
            <div className="text-xs text-neutral-500" data-testid="family-full">{t("family.full")}</div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
