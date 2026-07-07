import axios from "axios";

export const INSIGHT_API_URL = process.env.REACT_APP_INSIGHT_API_URL;

const api = axios.create({
  baseURL: INSIGHT_API_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach Bearer token from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("insight_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;