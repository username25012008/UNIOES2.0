// Единый клиент API: подставляет Bearer-токен, разбирает ошибки DRF.
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

const STORES = [localStorage, sessionStorage];

export const getToken = () =>
  STORES.map((s) => s.getItem("token")).find(Boolean) || null;

export const clearSession = () =>
<<<<<<< HEAD
  STORES.forEach((s) => ["token", "refresh", "user"].forEach((k) => s.removeItem(k)));

// Выход: refresh-токен отзывается на сервере, затем чистится локальная сессия
export async function logout() {
  const store = STORES.find((s) => s.getItem("refresh"));
  const refresh = store?.getItem("refresh");
  clearSession();
  if (refresh) {
    try {
      await fetch(`${API_URL}/auth/logout/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
    } catch { /* сервер недоступен — локальная сессия уже очищена */ }
  }
}

// Правила пароля (совпадают с серверным ComplexPasswordValidator)
export const PASSWORD_HINT = "Минимум 8 символов: заглавная и строчная буква, цифра и спецсимвол.";
export const passwordRules = [
  { required: true, message: "Введите пароль" },
  {
    validator: (_, v) => {
      if (!v) return Promise.resolve();
      const miss = [];
      if (v.length < 8) miss.push("минимум 8 символов");
      if (!/[A-ZА-ЯЁ]/.test(v)) miss.push("заглавную букву");
      if (!/[a-zа-яё]/.test(v)) miss.push("строчную букву");
      if (!/\d/.test(v)) miss.push("цифру");
      if (!/[^\w\s]|_/.test(v)) miss.push("спецсимвол (! @ # $ %)");
      return miss.length ? Promise.reject(new Error("Нужно: " + miss.join(", "))) : Promise.resolve();
    },
  },
];
=======
  STORES.forEach((s) => ["token", "user"].forEach((k) => s.removeItem(k)));
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc

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

<<<<<<< HEAD
// Обновляет access-токен по refresh-токену (один запрос на всех, пока идёт обновление)
let refreshing = null;
function refreshToken() {
  const store = STORES.find((s) => s.getItem("refresh"));
  if (!store) return Promise.resolve(false);
  refreshing ||= fetch(`${API_URL}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: store.getItem("refresh") }),
  })
    .then(async (r) => {
      if (!r.ok) return false;
      const d = await r.json();
      store.setItem("token", d.access);
      if (d.refresh) store.setItem("refresh", d.refresh);
      return true;
    })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
export async function api(path, { method = "GET", body, params } = {}) {
  const query = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
      )
    : "";

<<<<<<< HEAD
  const send = () =>
    fetch(`${API_URL}${path}${query}`, {
=======
  let res;
  try {
    res = await fetch(`${API_URL}${path}${query}`, {
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${getToken()}`,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
<<<<<<< HEAD

  let res;
  try {
    res = await send();
    // Access-токен живёт 15 минут: пробуем обновить и повторить запрос один раз
    if (res.status === 401 && (await refreshToken())) res = await send();
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
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
<<<<<<< HEAD

// Запрос с файлом/без JSON-тела (то же обновление токена, что и в api())
async function rawFetch(path, init = {}) {
  const send = () => fetch(`${API_URL}${path}`, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${getToken()}` } });
  let res;
  try {
    res = await send();
    if (res.status === 401 && (await refreshToken())) res = await send();
  } catch {
    throw new ApiError(0, "Сервер недоступен");
  }
  if (res.status === 401) {
    clearSession();
    window.location.href = "/login";
    throw new ApiError(401, "Сессия истекла");
  }
  return res;
}

// Загрузка файла (multipart); Content-Type выставит браузер
export async function uploadFile(path, file, field = "file") {
  const fd = new FormData();
  fd.append(field, file);
  const res = await rawFetch(path, { method: "POST", body: fd });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

// Скачивание файла с авторизацией
export async function downloadFile(path, filename) {
  const res = await rawFetch(path);
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null));
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
