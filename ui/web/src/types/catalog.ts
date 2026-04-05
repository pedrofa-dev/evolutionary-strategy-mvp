export type HealthStatus = {
  status: string;
};

export type CatalogItemOrigin = "runtime" | "asset" | "plugin";

export type CatalogItem = {
  id: string;
  category: string;
  origin: CatalogItemOrigin;
  file_path: string | null;
  description: string | null;
  payload: Record<string, unknown> | null;
};

export type CatalogPayload = Record<string, CatalogItem[]>;

export type CatalogCategoryPayload = {
  category: string;
  items: CatalogItem[];
};
