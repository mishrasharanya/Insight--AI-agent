import { useEffect, useState, useCallback } from "react";
import api, { INSIGHT_API_URL } from "./api";

export function useAuth() {
  const getTrialUser = () => (
    localStorage.getItem("insight_try_mode") === "true"
      ? { email: "Experimenting stage", isGuest: true }
      : null
  );
  const [user, setUser] = useState(() => getTrialUser());
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      localStorage.setItem("insight_token", urlToken);
      params.delete("token");
      const pendingPath = localStorage.getItem("insight_after_login");
      if (pendingPath) localStorage.removeItem("insight_after_login");
      const clean = pendingPath || (window.location.pathname + (params.toString() ? `?${params}` : ""));
      window.history.replaceState({}, "", clean);
      if (pendingPath) window.dispatchEvent(new PopStateEvent("popstate"));
    }

    try {
      const { data } = await api.get("/auth/me");
      setUser(data.logged_in ? { email: data.email } : getTrialUser());
    } catch {
      setUser(getTrialUser());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const login = (nextPath) => {
    localStorage.removeItem("insight_try_mode");
    if (nextPath) localStorage.setItem("insight_after_login", nextPath);
    window.location.href = `${INSIGHT_API_URL}/auth/google/login`;
  };

  const startTrial = () => {
    localStorage.removeItem("insight_token");
    localStorage.setItem("insight_try_mode", "true");
    setUser({ email: "Experimenting stage", isGuest: true });
  };

  const leaveTrial = () => {
    localStorage.removeItem("insight_try_mode");
    setUser(null);
  };

  const logout = async () => {
    localStorage.removeItem("insight_token");
    localStorage.removeItem("insight_chat");
    localStorage.removeItem("insight_try_mode");
    try { await api.post("/auth/logout"); } catch {}
    setUser(null);
    window.location.href = "/";
  };

  return { user, loading, login, logout, startTrial, leaveTrial };
}
