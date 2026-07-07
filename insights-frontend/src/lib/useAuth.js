import { useEffect, useState, useCallback } from "react";
import api, { INSIGHT_API_URL } from "./api";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // 1) If Google redirected us back with ?token=... store it and clean URL
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      localStorage.setItem("insight_token", urlToken);
      params.delete("token");
      const clean = window.location.pathname + (params.toString() ? `?${params}` : "");
      window.history.replaceState({}, "", clean);
    }

    // 2) Ask backend who we are
    try {
      const { data } = await api.get("/auth/me");
      if (data.logged_in) {
        setUser({ email: data.email });
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = () => {
    // Send user to backend's Google login endpoint
    window.location.href = `${INSIGHT_API_URL}/auth/google/login`;
  };

  const logout = async () => {
    localStorage.removeItem("insight_token");
    try {
      await api.post("/auth/logout");
    } catch {}
    setUser(null);
    window.location.href = "/";
  };

  return { user, loading, login, logout };
}