import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export const fileUrl = (path) => `${API}/files/${path}`;

const PROFILE_KEY = "atelier_active_profile";

export const getActiveProfile = () => {
  try { return localStorage.getItem(PROFILE_KEY); } catch { return null; }
};

export const setActiveProfile = (id) => {
  try {
    if (id) localStorage.setItem(PROFILE_KEY, id);
    else localStorage.removeItem(PROFILE_KEY);
  } catch (_e) { /* ignore */ }
};

export const basePhotoKey = () => {
  const p = getActiveProfile();
  return p ? `atelier_base_photo:${p}` : "atelier_base_photo";
};

api.interceptors.request.use((config) => {
  const p = getActiveProfile();
  if (p) config.headers["X-Profile-Id"] = p;
  return config;
});

export const SESSION_REVOKED_KEY = "atelier_session_revoked";

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401 && error.response.data?.detail === "session_revoked_other_device") {
      try { localStorage.setItem(SESSION_REVOKED_KEY, "1"); } catch (_e) { /* ignore */ }
      window.dispatchEvent(new Event("atelier-session-revoked"));
    }
    return Promise.reject(error);
  }
);
