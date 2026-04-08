import { useEffect, useMemo, useState } from "react";

import { getCatalog, getCatalogCategory, getHealth } from "./services/catalogApi";
import { getRunLabBootstrap } from "./services/runLabApi";
import DecisionPolicyModal from "./components/DecisionPolicyModal";
import GenomeSchemaModal from "./components/GenomeSchemaModal";
import GlobalExecutionMonitor from "./components/GlobalExecutionMonitor";
import MutationProfileModal from "./components/MutationProfileModal";
import SignalPackModal from "./components/SignalPackModal";
import type { CatalogItem, CatalogPayload } from "./types/catalog";
import CategoryPage from "./pages/CategoryPage";
import ConfigsPage from "./pages/ConfigsPage";
import DetailPage from "./pages/DetailPage";
import HomePage from "./pages/HomePage";
import OverviewPage from "./pages/OverviewPage";
import ResultsPage from "./pages/ResultsPage";
import RunLabPage from "./pages/RunLabPage";
import type {
  DecisionPolicyAuthoringMetadata,
  SavedDecisionPolicyAssetResult,
  GenomeSchemaAuthoringMetadata,
  SavedGenomeSchemaAssetResult,
  SavedMutationProfileAssetResult,
  SavedSignalPackAssetResult,
  SignalAuthoringOption,
} from "./types/runLab";

type Theme = "light" | "dark";
type Route =
  | { kind: "home" }
  | { kind: "configs"; configName: string | null }
  | { kind: "overview" }
  | { kind: "run-lab" }
  | { kind: "results"; campaignId: string | null }
  | { kind: "category"; category: string }
  | { kind: "detail"; category: string; itemId: string };

const THEME_STORAGE_KEY = "catalog-ui-theme";
const RESULTS_NAVIGATION_INTENT_KEY = "results-navigation-intent";

function parseRoute(pathname: string): Route {
  const cleanPath = pathname.replace(/\/+$/, "") || "/";
  const parts = cleanPath.split("/").filter(Boolean);

  if (parts.length === 0) {
    return { kind: "home" };
  }

  if (parts[0] === "configs") {
    return {
      kind: "configs",
      configName: parts.length >= 2 ? decodeURIComponent(parts[1]) : null,
    };
  }

  if (parts[0] === "run-lab") {
    return { kind: "run-lab" };
  }

  if (parts[0] === "results") {
    return {
      kind: "results",
      campaignId: parts.length >= 2 ? decodeURIComponent(parts[1]) : null,
    };
  }

  if (parts[0] !== "catalog") {
    return { kind: "home" };
  }

  if (parts.length === 1) {
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

  return { kind: "home" };
}

function navigate(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function openResultsWorkspace() {
  window.sessionStorage.removeItem(RESULTS_NAVIGATION_INTENT_KEY);
  navigate("/results");
}

function openResultsPath(campaignId?: string | null) {
  if (campaignId) {
    navigate(`/results/${encodeURIComponent(campaignId)}`);
    return;
  }
  navigate("/results");
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
  const [isCatalogMutationProfileModalOpen, setIsCatalogMutationProfileModalOpen] = useState(false);
  const [isCatalogSignalPackModalOpen, setIsCatalogSignalPackModalOpen] = useState(false);
  const [isCatalogGenomeSchemaModalOpen, setIsCatalogGenomeSchemaModalOpen] = useState(false);
  const [isCatalogDecisionPolicyModalOpen, setIsCatalogDecisionPolicyModalOpen] = useState(false);
  const [catalogSignalAuthoringOptions, setCatalogSignalAuthoringOptions] = useState<
    SignalAuthoringOption[]
  >([]);
  const [catalogGenomeSchemaAuthoring, setCatalogGenomeSchemaAuthoring] =
    useState<GenomeSchemaAuthoringMetadata | null>(null);
  const [catalogDecisionPolicyAuthoring, setCatalogDecisionPolicyAuthoring] =
    useState<DecisionPolicyAuthoringMetadata | null>(null);

  useEffect(() => {
    const onPopState = () => {
      setRoute(parseRoute(window.location.pathname));
    };

    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  async function refreshCatalogCategory(category: string) {
    try {
      setLoadingCategory(category);
      setError(null);
      const response = await getCatalogCategory(category);
      setCategoryItems((current) => ({
        ...current,
        [category]: response.items,
      }));
      setCatalog((current) => ({
        ...current,
        [category]: response.items,
      }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unknown error");
    } finally {
      setLoadingCategory((current) => (current === category ? null : current));
    }
  }

  async function handleCatalogMutationProfileSaved(_: SavedMutationProfileAssetResult) {
    await refreshCatalogCategory("mutation_profiles");
    setIsCatalogMutationProfileModalOpen(false);
  }

  async function handleCatalogSignalPackSaved(_: SavedSignalPackAssetResult) {
    await refreshCatalogCategory("signal_packs");
    setIsCatalogSignalPackModalOpen(false);
  }

  async function handleCatalogGenomeSchemaSaved(_: SavedGenomeSchemaAssetResult) {
    await refreshCatalogCategory("genome_schemas");
    setIsCatalogGenomeSchemaModalOpen(false);
  }

  async function handleCatalogDecisionPolicySaved(_: SavedDecisionPolicyAssetResult) {
    await refreshCatalogCategory("decision_policies");
    setIsCatalogDecisionPolicyModalOpen(false);
  }

  async function ensureCatalogAuthoringBootstrap() {
    const bootstrap = await getRunLabBootstrap();
    setCatalogSignalAuthoringOptions(bootstrap.signal_pack_authoring.signal_options);
    setCatalogGenomeSchemaAuthoring(bootstrap.genome_schema_authoring);
    setCatalogDecisionPolicyAuthoring(bootstrap.decision_policy_authoring);
    return bootstrap;
  }

  async function openCatalogSignalPackAuthoring() {
    try {
      setError(null);
      if (catalogSignalAuthoringOptions.length === 0) {
        await ensureCatalogAuthoringBootstrap();
      }
      setIsCatalogSignalPackModalOpen(true);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unknown error");
    }
  }

  async function openCatalogGenomeSchemaAuthoring() {
    try {
      setError(null);
      if (!catalogGenomeSchemaAuthoring) {
        await ensureCatalogAuthoringBootstrap();
      }
      setIsCatalogGenomeSchemaModalOpen(true);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unknown error");
    }
  }

  async function openCatalogDecisionPolicyAuthoring() {
    try {
      setError(null);
      if (!catalogDecisionPolicyAuthoring) {
        await ensureCatalogAuthoringBootstrap();
      }
      setIsCatalogDecisionPolicyModalOpen(true);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unknown error");
    }
  }

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

  const categoryAuthoringAction =
    route.kind === "category"
      ? route.category === "mutation_profiles"
        ? {
            label: "New mutation profile",
            onClick: () => setIsCatalogMutationProfileModalOpen(true),
          }
        : route.category === "signal_packs"
          ? {
              label: "New signal pack",
              onClick: () => void openCatalogSignalPackAuthoring(),
            }
          : route.category === "genome_schemas"
            ? {
                label: "New genome schema",
                onClick: () => void openCatalogGenomeSchemaAuthoring(),
              }
            : route.category === "decision_policies"
              ? {
                  label: "New decision policy",
                  onClick: () => void openCatalogDecisionPolicyAuthoring(),
                }
          : null
      : null;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-content">
          <div className="app-header-left">
            <button className="brand-button" onClick={() => navigate("/")} type="button">
              Experimental Lab UI
            </button>
            <nav className="top-nav" aria-label="Primary">
              <button
                className={route.kind === "home" ? "top-nav-button active" : "top-nav-button"}
                onClick={() => navigate("/")}
                type="button"
              >
                Home
              </button>
              <button
                className={route.kind === "run-lab" ? "top-nav-button active" : "top-nav-button"}
                onClick={() => navigate("/run-lab")}
                type="button"
              >
                Run Lab
              </button>
              <button
                className={route.kind === "configs" ? "top-nav-button active" : "top-nav-button"}
                onClick={() => navigate("/configs")}
                type="button"
              >
                Configs
              </button>
              <button
                className={route.kind === "results" ? "top-nav-button active" : "top-nav-button"}
                onClick={openResultsWorkspace}
                type="button"
              >
                Runs / Results
              </button>
              <button
                className={route.kind === "overview" || route.kind === "category" || route.kind === "detail" ? "top-nav-button active" : "top-nav-button"}
                onClick={() => navigate("/catalog")}
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

        {route.kind === "home" ? (
          <HomePage
            onOpenRunLab={() => navigate("/run-lab")}
            onOpenConfigs={() => navigate("/configs")}
            onOpenResults={(campaignId) => openResultsPath(campaignId)}
            onOpenCatalog={() => navigate("/catalog")}
            onOpenGenomeSchemaAuthoring={() => void openCatalogGenomeSchemaAuthoring()}
            onOpenMutationProfileAuthoring={() => setIsCatalogMutationProfileModalOpen(true)}
            onOpenDecisionPolicyAuthoring={() => void openCatalogDecisionPolicyAuthoring()}
            onOpenSignalPackAuthoring={() => void openCatalogSignalPackAuthoring()}
          />
        ) : null}

        {route.kind === "configs" ? (
          <ConfigsPage
            selectedConfigName={route.configName}
            onOpenConfig={(configName) => navigate(`/configs/${encodeURIComponent(configName)}`)}
            onOpenBrowser={() => navigate("/configs")}
          />
        ) : null}

        {route.kind === "overview" ? (
          <OverviewPage
            healthStatus={healthStatus}
            categories={categories}
            isLoading={isOverviewLoading}
            onOpenCategory={(category) => navigate(`/catalog/${encodeURIComponent(category)}`)}
            onOpenRunLab={() => navigate("/run-lab")}
          />
        ) : null}

        {route.kind === "run-lab" ? (
          <RunLabPage
            onOpenCatalog={() => navigate("/catalog")}
            onOpenResults={(campaignId) => openResultsPath(campaignId)}
          />
        ) : null}

        {route.kind === "results" ? (
          <ResultsPage
            selectedCampaignId={route.campaignId}
            onOpenCampaign={(campaignId) =>
              navigate(`/results/${encodeURIComponent(campaignId)}`)
            }
            onOpenWorkspace={openResultsWorkspace}
            onOpenRunLab={() => navigate("/run-lab")}
          />
        ) : null}

        {route.kind === "category" ? (
          <CategoryPage
            categories={categories}
            selectedCategory={route.category}
            items={currentItems}
            isLoading={isCategoryLoading}
            authoringAction={categoryAuthoringAction}
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
            onBackToOverview={() => navigate("/catalog")}
          />
        ) : null}
      </main>

      <MutationProfileModal
        contextLabel="Catalog Authoring"
        isOpen={isCatalogMutationProfileModalOpen}
        onClose={() => setIsCatalogMutationProfileModalOpen(false)}
        onSaved={handleCatalogMutationProfileSaved}
      />
      <SignalPackModal
        contextLabel="Catalog Authoring"
        isOpen={isCatalogSignalPackModalOpen}
        onClose={() => setIsCatalogSignalPackModalOpen(false)}
        onSaved={handleCatalogSignalPackSaved}
        signalOptions={catalogSignalAuthoringOptions}
      />
      <GenomeSchemaModal
        contextLabel="Catalog Authoring"
        isOpen={isCatalogGenomeSchemaModalOpen}
        onClose={() => setIsCatalogGenomeSchemaModalOpen(false)}
        onSaved={handleCatalogGenomeSchemaSaved}
        geneCatalogOptions={
          catalogGenomeSchemaAuthoring?.gene_catalog_options ?? []
        }
        geneTypeOptions={catalogGenomeSchemaAuthoring?.gene_type_options ?? []}
        suggestedModules={catalogGenomeSchemaAuthoring?.suggested_modules ?? []}
      />
      <DecisionPolicyModal
        contextLabel="Catalog Authoring"
        isOpen={isCatalogDecisionPolicyModalOpen}
        onClose={() => setIsCatalogDecisionPolicyModalOpen(false)}
        onSaved={handleCatalogDecisionPolicySaved}
        authoring={
          catalogDecisionPolicyAuthoring ?? {
            engine_options: [],
            entry_signal_options: [],
            weight_gene_field_options: [],
            fixed_gene_bindings: {
              entry_trigger_gene: "",
              exit_policy_gene: "",
              trade_control_gene: "",
            },
          }
        }
      />
      <GlobalExecutionMonitor onOpenResultsPath={(path) => navigate(path)} />
    </div>
  );
}
