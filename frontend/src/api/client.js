import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000
});

export function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}
