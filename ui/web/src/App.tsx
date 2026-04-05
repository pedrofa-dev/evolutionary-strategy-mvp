import { useEffect, useMemo, useState } from "react";

import { getCatalog, getCatalogCategory, getHealth } from "./services/catalogApi";
import type { CatalogItem, CatalogPayload } from "./types/catalog";
import CategoryPage from "./pages/CategoryPage";
import DetailPage from "./pages/DetailPage";
import OverviewPage from "./pages/OverviewPage";
import RunLabPage from "./pages/RunLabPage";

type Theme = "light" | "dark";
type Route =
  | { kind: "overview" }
  | { kind: "run-lab" }
  | { kind: "category"; category: string }
  | { kind: "detail"; category: string; itemId: string };

const THEME_STORAGE_KEY = "catalog-ui-theme";

function parseRoute(pathname: string): Route {
  const cleanPath = pathname.replace(/\/+$/, "") || "/";
  const parts = cleanPath.split("/").filter(Boolean);

  if (parts.length === 0) {
    return { kind: "overview" };
  }

  if (parts[0] === "run-lab") {
    return { kind: "run-lab" };
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

function getSystemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredThemePreference(): Theme | null {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (storedTheme === "light" || storedTheme === "dark") {
    return storedTheme;
  }
  return null;
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname));
  const [themePreference, setThemePreference] = useState<Theme | null>(() => getStoredThemePreference());
  const [systemTheme, setSystemTheme] = useState<Theme>(() => getSystemTheme());
  const [healthStatus, setHealthStatus] = useState("checking");
  const [catalog, setCatalog] = useState<CatalogPayload>({});
  const [categoryItems, setCategoryItems] = useState<Record<string, CatalogItem[]>>({});
  const [isOverviewLoading, setIsOverviewLoading] = useState(true);
  const [loadingCategory, setLoadingCategory] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onPopState = () => {
      setRoute(parseRoute(window.location.pathname));
    };

    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const theme = themePreference ?? systemTheme;

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(theme);
    document.body.classList.remove("light", "dark");
    document.body.classList.add(theme);
    if (themePreference) {
      window.localStorage.setItem(THEME_STORAGE_KEY, themePreference);
    } else {
      window.localStorage.removeItem(THEME_STORAGE_KEY);
    }
  }, [theme, themePreference]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      setSystemTheme(mediaQuery.matches ? "dark" : "light");
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadOverview() {
      try {
        setIsOverviewLoading(true);
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
      } finally {
        if (!cancelled) {
          setIsOverviewLoading(false);
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
        setLoadingCategory(category);
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
      } finally {
        if (!cancelled) {
          setLoadingCategory((current) => (current === category ? null : current));
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

  const isCategoryLoading =
    (route.kind === "category" || route.kind === "detail") && loadingCategory === route.category;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-content">
          <div className="app-header-left">
            <button className="brand-button" onClick={() => navigate("/run-lab")} type="button">
              Experimental Lab UI
            </button>
            <nav className="top-nav" aria-label="Primary">
              <button
                className={route.kind === "run-lab" ? "top-nav-button active" : "top-nav-button"}
                onClick={() => navigate("/run-lab")}
                type="button"
              >
                Run Lab
              </button>
              <button
                className={route.kind === "overview" || route.kind === "category" || route.kind === "detail" ? "top-nav-button active" : "top-nav-button"}
                onClick={() => navigate("/")}
                type="button"
              >
                Catalog
              </button>
            </nav>
          </div>
          <button
            className="theme-toggle"
            onClick={() => setThemePreference(theme === "dark" ? "light" : "dark")}
            type="button"
          >
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </header>

      <main className="app-main">
        {error ? <div className="error-banner">{error}</div> : null}

        {route.kind === "overview" ? (
          <OverviewPage
            healthStatus={healthStatus}
            categories={categories}
            isLoading={isOverviewLoading}
            onOpenCategory={(category) => navigate(`/catalog/${encodeURIComponent(category)}`)}
            onOpenRunLab={() => navigate("/run-lab")}
          />
        ) : null}

        {route.kind === "run-lab" ? <RunLabPage onOpenCatalog={() => navigate("/")} /> : null}

        {route.kind === "category" ? (
          <CategoryPage
            categories={categories}
            selectedCategory={route.category}
            items={currentItems}
            isLoading={isCategoryLoading}
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
            category={route.category}
            isLoading={isCategoryLoading}
            missingItemId={selectedItem ? null : route.itemId}
            onBackToCategory={(category) => navigate(`/catalog/${encodeURIComponent(category)}`)}
            onBackToOverview={() => navigate("/")}
          />
        ) : null}
      </main>
    </div>
  );
}
