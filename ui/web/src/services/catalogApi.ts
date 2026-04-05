import type {
  CatalogCategoryPayload,
  CatalogPayload,
  HealthStatus,
} from "../types/catalog";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Request failed (${response.status}): ${errorBody}`);
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthStatus> {
  return requestJson<HealthStatus>("/health");
}

export function getCatalog(): Promise<CatalogPayload> {
  return requestJson<CatalogPayload>("/catalog");
}

export function getCatalogCategory(category: string): Promise<CatalogCategoryPayload> {
  return requestJson<CatalogCategoryPayload>(`/catalog/${category}`);
}
