// Единый клиент API: подставляет Bearer-токен, разбирает ошибки DRF.
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

const STORES = [localStorage, sessionStorage];

export const getToken = () =>
  STORES.map((s) => s.getItem("token")).find(Boolean) || null;

export const clearSession = () =>
  STORES.forEach((s) => ["token", "user"].forEach((k) => s.removeItem(k)));

export class ApiError extends Error {
  constructor(status, data) {
    super(errorText(data) || `Ошибка ${status}`);
    this.status = status;
    this.data = data;
  }
}

// Превращает ответ DRF ({field: ["msg"]}, {detail, problems}) в читаемый текст
export function errorText(data) {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(errorText).join(". ");
  if (data.problems?.length) {
    return `${data.detail}: ${data.problems.join("; ")}`;
  }
  if (data.detail) return errorText(data.detail);
  return Object.entries(data)
    .map(([k, v]) => `${k}: ${errorText(v)}`)
    .join(". ");
}

export async function api(path, { method = "GET", body, params } = {}) {
  const query = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
      )
    : "";

  let res;
  try {
    res = await fetch(`${API_URL}${path}${query}`, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${getToken()}`,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Сервер недоступен");
  }

  // Токен истёк или недействителен — на страницу входа
  if (res.status === 401) {
    clearSession();
    window.location.href = "/login";
    throw new ApiError(401, "Сессия истекла");
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}
