const BASE_URL = import.meta.env.VITE_API_BASE_URL || "https://ai-based-mplods-analysis.onrender.com";
const TOKEN_KEY = "mplads_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body, isForm = false, params } = {}) {
  const token = getToken();
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body && !isForm) headers["Content-Type"] = "application/json";

  let url = `${BASE_URL}${path.startsWith('/') ? path : '/' + path}`;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    if (qs) url += `?${qs}`;
  }

  let res;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new ApiError("Cannot reach the server. Is the backend running on Render?", 0);
  }

  if (res.status === 401) {
    setToken(null);
    window.location.href = "/login";
    throw new ApiError("Session expired — please log in again", 401);
  }

  const contentType = res.headers.get("content-type") || "";
  let data;
  try {
    data = contentType.includes("application/json") ? await res.json() : await res.text();
  } catch {
    throw new ApiError(`Server returned an unexpected response (HTTP ${res.status}).`, res.status);
  }

  if (!res.ok) {
    const detail = typeof data === "object" && data?.detail ? data.detail : `Request failed (${res.status})`;
    throw new ApiError(detail, res.status);
  }
  return data;
}

export const api = {
  get: (path, params) => request(path, { method: "GET", params }),
  post: (path, body) => request(path, { method: "POST", body }),
  postForm: (path, formData) => request(path, { method: "POST", body: formData, isForm: true }),
};

export async function login(username, password) {
  const form = new URLSearchParams({ username, password });
  let res;
  try {
    res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running on Render?", 0);
  }

  let data;
  try {
    data = await res.json();
  } catch {
    throw new ApiError(`Server returned an unexpected response (HTTP ${res.status}). Is the backend running correctly?`, res.status);
  }

  if (!res.ok) throw new ApiError(data.detail || "Login failed", res.status);
  return data;
}