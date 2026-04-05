import { useEffect, useMemo, useState } from "react";

import { getCatalog, getCatalogCategory, getHealth } from "./services/catalogApi";
import type { CatalogItem, CatalogPayload } from "./types/catalog";
import CategoryPage from "./pages/CategoryPage";
import DetailPage from "./pages/DetailPage";
import OverviewPage from "./pages/OverviewPage";

type Route =
  | { kind: "overview" }
  | { kind: "category"; category: string }
  | { kind: "detail"; category: string; itemId: string };

function parseRoute(pathname: string): Route {
  const cleanPath = pathname.replace(/\/+$/, "") || "/";
  const parts = cleanPath.split("/").filter(Boolean);

  if (parts.length === 0) {
    return { kind: "overview" };
  }

  if (parts[0] !== "catalog") {
    return { kind: "overview" };
  }

  if (parts.length === 2) {
    return { kind: "category", category: decodeURIComponent(parts[1]) };
  }

  if (parts.length >= 3) {
    return {
      kind: "detail",
      category: decodeURIComponent(parts[1]),
      itemId: decodeURIComponent(parts[2]),
    };
  }

  return { kind: "overview" };
}

function navigate(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname));
  const [healthStatus, setHealthStatus] = useState("checking");
  const [catalog, setCatalog] = useState<CatalogPayload>({});
  const [categoryItems, setCategoryItems] = useState<Record<string, CatalogItem[]>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onPopState = () => {
      setRoute(parseRoute(window.location.pathname));
    };

    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadOverview() {
      try {
        setError(null);
        const [health, nextCatalog] = await Promise.all([getHealth(), getCatalog()]);
        if (!cancelled) {
          setHealthStatus(health.status);
          setCatalog(nextCatalog);
        }
      } catch (loadError) {
        if (!cancelled) {
          setHealthStatus("error");
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      }
    }

    void loadOverview();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadCategory(category: string) {
      if (categoryItems[category]) {
        return;
      }

      try {
        setError(null);
        const response = await getCatalogCategory(category);
        if (!cancelled) {
          setCategoryItems((current) => ({
            ...current,
            [category]: response.items,
          }));
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      }
    }

    if (route.kind === "category" || route.kind === "detail") {
      void loadCategory(route.category);
    }

    return () => {
      cancelled = true;
    };
  }, [categoryItems, route]);

  const categories = useMemo(() => Object.keys(catalog).sort(), [catalog]);

  const currentItems =
    route.kind === "category" || route.kind === "detail"
      ? categoryItems[route.category] ?? catalog[route.category] ?? []
      : [];

  const selectedItem =
    route.kind === "detail"
      ? currentItems.find((item) => item.id === route.itemId) ?? null
      : null;

  return (
    <div className="app-shell">
      <header className="app-header">
        <button className="brand-button" onClick={() => navigate("/")} type="button">
          Experimental Catalog UI
        </button>
      </header>

      <main className="app-main">
        {error ? <div className="error-banner">{error}</div> : null}

        {route.kind === "overview" ? (
          <OverviewPage
            healthStatus={healthStatus}
            categories={categories}
            onOpenCategory={(category) => navigate(`/catalog/${encodeURIComponent(category)}`)}
          />
        ) : null}

        {route.kind === "category" ? (
          <CategoryPage
            categories={categories}
            selectedCategory={route.category}
            items={currentItems}
            onSelectCategory={(category) => navigate(`/catalog/${encodeURIComponent(category)}`)}
            onOpenItem={(item) =>
              navigate(
                `/catalog/${encodeURIComponent(item.category)}/${encodeURIComponent(item.id)}`,
              )
            }
          />
        ) : null}

        {route.kind === "detail" ? (
          <DetailPage
            item={selectedItem}
            onBackToCategory={(category) => navigate(`/catalog/${encodeURIComponent(category)}`)}
          />
        ) : null}
      </main>
    </div>
  );
}
