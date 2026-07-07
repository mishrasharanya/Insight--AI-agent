import axios from "axios";

// Base URL for the Insight Agent backend hosted on Render.
// Auth uses cookies, so withCredentials must be true on every request.
export const INSIGHT_API_URL = process.env.REACT_APP_INSIGHT_API_URL;

const api = axios.create({
  baseURL: INSIGHT_API_URL,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export default api;