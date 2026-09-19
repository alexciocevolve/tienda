const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// What every failed call throws. `status` is 0 when the server could not be reached at all.
export type ApiError = { status: number; detail: string };

// Every call to the API goes through here, so errors look the same everywhere.
export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE + path, options);
  } catch {
    throw { status: 0, detail: "Could not reach the server" } satisfies ApiError;
  }
  if (!response.ok) {
    // The API always answers errors as {"detail": "..."}
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw { status: response.status, detail } satisfies ApiError;
  }
  return response.json() as Promise<T>;
}
