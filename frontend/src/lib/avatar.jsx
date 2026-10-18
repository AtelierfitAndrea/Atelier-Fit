import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const Ctx = createContext({ avatar: null, loading: true, refresh: () => {}, setAvatar: () => {} });

export function AvatarProvider({ children }) {
  const { user } = useAuth();
  const [avatar, setAvatar] = useState(null);
  const [loading, setLoading] = useState(true);
  const [profileName, setProfileName] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/profile/avatar");
      setAvatar(data?.path ? data : null);
      setProfileName(data?.profile_name || null);
    } catch { setAvatar(null); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (user) refresh(); else { setAvatar(null); setLoading(false); } }, [user, refresh]);

  return <Ctx.Provider value={{ avatar, loading, refresh, setAvatar, profileName }}>{children}</Ctx.Provider>;
}

export const useAvatar = () => useContext(Ctx);
