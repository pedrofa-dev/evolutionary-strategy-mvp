import { useEffect, useMemo, useState } from "react";

import {
  duplicateConfig,
  getConfig,
  getConfigs,
  renameConfig,
  saveConfig,
  saveConfigAsNew,
} from "../services/configsApi";
import type { RunConfigBrowserSummary, RunConfigEditorView } from "../types/configs";

type ConfigsPageProps = {
  selectedConfigName: string | null;
  onOpenConfig: (configName: string) => void;
  onOpenBrowser: () => void;
};

type OperationState =
  | { kind: "duplicate"; sourceConfigName: string }
  | { kind: "rename"; sourceConfigName: string }
  | null;

type EditableConfigForm = {
  identity: { config_name: string; config_path: string };
  research_stack: Record<string, string>;
  evolution_budget: Record<string, string>;
  seed_plan: { mode: string; seed_start: string; seed_count: string; explicit_seeds: string };
  evaluation_trading: {
    trade_cost_rate: string;
    cost_penalty_weight: string;
    trade_count_penalty_weight: string;
    entry_score_margin: string;
    min_bars_between_entries: string;
    entry_confirmation_bars: string;
    regime_filter_enabled: boolean;
    min_trend_long_for_entry: string;
    min_breakout_for_entry: string;
    max_realized_volatility_for_entry: string;
  };
  advanced_overrides: Record<string, string>;
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Not used yet";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function formatStatus(value: string | null | undefined): string {
  return value ? value.replace(/[_-]+/g, " ") : "Not used";
}

function detailJson(value: Record<string, unknown>): string {
  return Object.keys(value).length === 0 ? "{}" : JSON.stringify(value, null, 2);
}

function buildEditableForm(detail: RunConfigEditorView): EditableConfigForm {
  return {
    identity: {
      config_name: detail.identity.config_name,
      config_path: detail.identity.config_path,
    },
    research_stack: {
      dataset_catalog_id: detail.research_stack.dataset_catalog_id,
      signal_pack_name: detail.research_stack.signal_pack_name,
      genome_schema_name: detail.research_stack.genome_schema_name,
      decision_policy_name: detail.research_stack.decision_policy_name,
      mutation_profile_name: detail.research_stack.mutation_profile_name,
      market_mode_name: detail.research_stack.market_mode_name,
      leverage: String(detail.research_stack.leverage),
    },
    evolution_budget: {
      mutation_seed: String(detail.evolution_budget.mutation_seed),
      population_size: String(detail.evolution_budget.population_size),
      target_population_size: String(detail.evolution_budget.target_population_size),
      survivors_count: String(detail.evolution_budget.survivors_count),
      generations_planned: String(detail.evolution_budget.generations_planned),
    },
    seed_plan: {
      mode: detail.seed_plan.mode,
      seed_start: detail.seed_plan.seed_start == null ? "" : String(detail.seed_plan.seed_start),
      seed_count: detail.seed_plan.seed_count == null ? "" : String(detail.seed_plan.seed_count),
      explicit_seeds: detail.seed_plan.explicit_seeds.join(", "),
    },
    evaluation_trading: {
      trade_cost_rate: String(detail.evaluation_trading.trade_cost_rate),
      cost_penalty_weight: String(detail.evaluation_trading.cost_penalty_weight),
      trade_count_penalty_weight: String(detail.evaluation_trading.trade_count_penalty_weight),
      entry_score_margin: String(detail.evaluation_trading.entry_score_margin),
      min_bars_between_entries: String(detail.evaluation_trading.min_bars_between_entries),
      entry_confirmation_bars: String(detail.evaluation_trading.entry_confirmation_bars),
      regime_filter_enabled: detail.evaluation_trading.regime_filter_enabled,
      min_trend_long_for_entry: String(detail.evaluation_trading.min_trend_long_for_entry),
      min_breakout_for_entry: String(detail.evaluation_trading.min_breakout_for_entry),
      max_realized_volatility_for_entry:
        detail.evaluation_trading.max_realized_volatility_for_entry == null
          ? ""
          : String(detail.evaluation_trading.max_realized_volatility_for_entry),
    },
    advanced_overrides: {
      mutation_profile: detailJson(detail.advanced_overrides.mutation_profile),
      entry_trigger: detailJson(detail.advanced_overrides.entry_trigger),
      exit_policy: detailJson(detail.advanced_overrides.exit_policy),
      trade_control: detailJson(detail.advanced_overrides.trade_control),
      entry_trigger_constraints: detailJson(detail.advanced_overrides.entry_trigger_constraints),
    },
  };
}

function parseRequiredNumber(value: string, label: string): number {
  const trimmed = value.trim();
  if (!trimmed) throw new Error(`${label} is required.`);
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) throw new Error(`${label} must be a valid number.`);
  return parsed;
}

function parseOptionalNumber(value: string, label: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) throw new Error(`${label} must be a valid number.`);
  return parsed;
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  const trimmed = value.trim();
  if (!trimmed) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed) as unknown;
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

function buildSeedSummary(mode: string, seedStart: number | null, seedCount: number | null, explicitSeeds: number[]): string {
  if (mode === "explicit") return explicitSeeds.join(", ");
  if (mode === "range" && seedStart != null && seedCount != null) {
    return `${seedStart}-${seedStart + seedCount - 1} (${seedCount} seeds)`;
  }
  return "Runtime default seed plan";
}

function serializeEditorForm(form: EditableConfigForm, recentUsage: RunConfigEditorView["recent_usage"]): RunConfigEditorView {
  const configName = form.identity.config_name.trim();
  if (!configName) throw new Error("Config name is required.");

  const mode = form.seed_plan.mode || "runtime_default";
  let explicitSeeds: number[] = [];
  let seedStart: number | null = null;
  let seedCount: number | null = null;
  if (mode === "explicit") {
    explicitSeeds = form.seed_plan.explicit_seeds
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean)
      .map((value) => {
        const parsed = Number(value);
        if (!Number.isInteger(parsed)) throw new Error("Explicit seeds must be comma-separated integers.");
        return parsed;
      });
    if (explicitSeeds.length === 0) throw new Error("Explicit seed mode requires at least one explicit seed.");
  } else if (mode === "range") {
    seedStart = parseRequiredNumber(form.seed_plan.seed_start, "Seed start");
    seedCount = parseRequiredNumber(form.seed_plan.seed_count, "Seed count");
  } else if (mode !== "runtime_default") {
    throw new Error(`Unsupported seed mode: ${mode}`);
  }

  return {
    identity: { config_name: configName, config_path: form.identity.config_path },
    research_stack: {
      dataset_catalog_id: form.research_stack.dataset_catalog_id.trim(),
      signal_pack_name: form.research_stack.signal_pack_name.trim(),
      genome_schema_name: form.research_stack.genome_schema_name.trim(),
      decision_policy_name: form.research_stack.decision_policy_name.trim(),
      mutation_profile_name: form.research_stack.mutation_profile_name.trim(),
      market_mode_name: form.research_stack.market_mode_name.trim(),
      leverage: parseRequiredNumber(form.research_stack.leverage, "Leverage"),
    },
    evolution_budget: {
      mutation_seed: parseRequiredNumber(form.evolution_budget.mutation_seed, "Mutation seed"),
      population_size: parseRequiredNumber(form.evolution_budget.population_size, "Population size"),
      target_population_size: parseRequiredNumber(form.evolution_budget.target_population_size, "Target population size"),
      survivors_count: parseRequiredNumber(form.evolution_budget.survivors_count, "Survivors count"),
      generations_planned: parseRequiredNumber(form.evolution_budget.generations_planned, "Generations planned"),
    },
    seed_plan: {
      mode,
      seed_start: seedStart,
      seed_count: seedCount,
      explicit_seeds: explicitSeeds,
      summary: buildSeedSummary(mode, seedStart, seedCount, explicitSeeds),
    },
    evaluation_trading: {
      trade_cost_rate: parseRequiredNumber(form.evaluation_trading.trade_cost_rate, "Trade cost rate"),
      cost_penalty_weight: parseRequiredNumber(form.evaluation_trading.cost_penalty_weight, "Cost penalty weight"),
      trade_count_penalty_weight: parseRequiredNumber(form.evaluation_trading.trade_count_penalty_weight, "Trade count penalty weight"),
      entry_score_margin: parseRequiredNumber(form.evaluation_trading.entry_score_margin, "Entry score margin"),
      min_bars_between_entries: parseRequiredNumber(form.evaluation_trading.min_bars_between_entries, "Min bars between entries"),
      entry_confirmation_bars: parseRequiredNumber(form.evaluation_trading.entry_confirmation_bars, "Entry confirmation bars"),
      regime_filter_enabled: form.evaluation_trading.regime_filter_enabled,
      min_trend_long_for_entry: parseRequiredNumber(form.evaluation_trading.min_trend_long_for_entry, "Min trend long for entry"),
      min_breakout_for_entry: parseRequiredNumber(form.evaluation_trading.min_breakout_for_entry, "Min breakout for entry"),
      max_realized_volatility_for_entry: parseOptionalNumber(form.evaluation_trading.max_realized_volatility_for_entry, "Max realized volatility"),
    },
    advanced_overrides: {
      mutation_profile: parseJsonObject(form.advanced_overrides.mutation_profile, "Mutation profile payload"),
      entry_trigger: parseJsonObject(form.advanced_overrides.entry_trigger, "Entry trigger overrides"),
      exit_policy: parseJsonObject(form.advanced_overrides.exit_policy, "Exit policy overrides"),
      trade_control: parseJsonObject(form.advanced_overrides.trade_control, "Trade control overrides"),
      entry_trigger_constraints: parseJsonObject(form.advanced_overrides.entry_trigger_constraints, "Entry trigger constraints"),
    },
    recent_usage: recentUsage,
  };
}

export default function ConfigsPage({
  selectedConfigName,
  onOpenConfig,
  onOpenBrowser,
}: ConfigsPageProps) {
  const [configs, setConfigs] = useState<RunConfigBrowserSummary[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<RunConfigEditorView | null>(null);
  const [editorForm, setEditorForm] = useState<EditableConfigForm | null>(null);
  const [loadedConfigName, setLoadedConfigName] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDataset, setSelectedDataset] = useState("all");
  const [selectedSignalPack, setSelectedSignalPack] = useState("all");
  const [selectedGenomeSchema, setSelectedGenomeSchema] = useState("all");
  const [selectedDecisionPolicy, setSelectedDecisionPolicy] = useState("all");
  const [selectedMutationProfile, setSelectedMutationProfile] = useState("all");
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [operation, setOperation] = useState<OperationState>(null);
  const [operationName, setOperationName] = useState("");
  const [isSubmittingOperation, setIsSubmittingOperation] = useState(false);
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadConfigs() {
      try {
        setIsLoadingList(true);
        setError(null);
        const items = await getConfigs();
        if (!cancelled) setConfigs(items);
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : "Unknown error");
      } finally {
        if (!cancelled) setIsLoadingList(false);
      }
    }
    void loadConfigs();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadDetail(configName: string) {
      try {
        setIsLoadingDetail(true);
        setError(null);
        const detail = await getConfig(configName);
        if (!cancelled) {
          setSelectedConfig(detail);
          setEditorForm(buildEditableForm(detail));
          setLoadedConfigName(detail.identity.config_name);
        }
      } catch (loadError) {
        if (!cancelled) {
          setSelectedConfig(null);
          setEditorForm(null);
          setLoadedConfigName(null);
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      } finally {
        if (!cancelled) setIsLoadingDetail(false);
      }
    }

    if (!selectedConfigName) {
      setSelectedConfig(null);
      setEditorForm(null);
      setLoadedConfigName(null);
      return () => {
        cancelled = true;
      };
    }

    void loadDetail(selectedConfigName);
    return () => {
      cancelled = true;
    };
  }, [selectedConfigName]);

  const datasetOptions = useMemo(() => ["all", ...new Set(configs.map((item) => item.dataset_catalog_id))], [configs]);
  const signalPackOptions = useMemo(() => ["all", ...new Set(configs.map((item) => item.signal_pack_name))], [configs]);
  const genomeSchemaOptions = useMemo(() => ["all", ...new Set(configs.map((item) => item.genome_schema_name))], [configs]);
  const decisionPolicyOptions = useMemo(() => ["all", ...new Set(configs.map((item) => item.decision_policy_name))], [configs]);
  const mutationProfileOptions = useMemo(() => ["all", ...new Set(configs.map((item) => item.mutation_profile_name))], [configs]);

  const filteredConfigs = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    return configs.filter((item) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        [
          item.config_name,
          item.dataset_catalog_id,
          item.signal_pack_name,
          item.genome_schema_name,
          item.decision_policy_name,
          item.mutation_profile_name,
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery);
      if (!matchesQuery) return false;
      if (selectedDataset !== "all" && item.dataset_catalog_id !== selectedDataset) return false;
      if (selectedSignalPack !== "all" && item.signal_pack_name !== selectedSignalPack) return false;
      if (selectedGenomeSchema !== "all" && item.genome_schema_name !== selectedGenomeSchema) return false;
      if (selectedDecisionPolicy !== "all" && item.decision_policy_name !== selectedDecisionPolicy) return false;
      if (selectedMutationProfile !== "all" && item.mutation_profile_name !== selectedMutationProfile) return false;
      return true;
    });
  }, [configs, searchQuery, selectedDataset, selectedSignalPack, selectedGenomeSchema, selectedDecisionPolicy, selectedMutationProfile]);

  const isDirty = useMemo(() => {
    if (!selectedConfig || !editorForm) return false;
    try {
      return JSON.stringify(serializeEditorForm(editorForm, selectedConfig.recent_usage)) !== JSON.stringify(selectedConfig);
    } catch {
      return true;
    }
  }, [editorForm, selectedConfig]);

  function beginOperation(nextOperation: NonNullable<OperationState>) {
    setSuccessMessage(null);
    setError(null);
    setOperation(nextOperation);
    const stem = nextOperation.sourceConfigName.replace(/\.json$/i, "");
    setOperationName(nextOperation.kind === "duplicate" ? `${stem}_copy` : stem);
  }

  function closeOperation() {
    setOperation(null);
    setOperationName("");
    setIsSubmittingOperation(false);
  }

  async function refreshConfigsAndSelection(nextSelectedConfigName?: string | null) {
    const items = await getConfigs();
    setConfigs(items);
    const targetConfigName =
      nextSelectedConfigName ??
      (selectedConfigName && items.some((item) => item.config_name === selectedConfigName) ? selectedConfigName : null);
    if (targetConfigName) onOpenConfig(targetConfigName);
    else onOpenBrowser();
  }

  async function submitOperation() {
    if (!operation || !operationName.trim()) return;
    try {
      setIsSubmittingOperation(true);
      setError(null);
      setSuccessMessage(null);
      if (operation.kind === "duplicate") {
        const result = await duplicateConfig(operation.sourceConfigName, operationName.trim());
        await refreshConfigsAndSelection(result.config_name);
        setSuccessMessage(`Duplicated as ${result.config_name}.`);
      } else {
        const result = await renameConfig(operation.sourceConfigName, operationName.trim());
        await refreshConfigsAndSelection(result.config_name);
        setSuccessMessage(`Renamed to ${result.config_name}.`);
      }
      closeOperation();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unknown error");
      setIsSubmittingOperation(false);
    }
  }

  function updateEditorForm(updater: (current: EditableConfigForm) => EditableConfigForm) {
    setEditorForm((current) => (current ? updater(current) : current));
  }

  async function handleSaveCurrentConfig() {
    if (!editorForm || !loadedConfigName || !selectedConfig) return;
    try {
      setIsSavingConfig(true);
      setError(null);
      setSuccessMessage(null);
      if (editorForm.identity.config_name.trim() !== loadedConfigName) {
        throw new Error("Save cannot rename the config implicitly. Use Save as new or Rename instead.");
      }
      const saved = await saveConfig(
        loadedConfigName,
        serializeEditorForm(editorForm, selectedConfig.recent_usage),
      );
      setSelectedConfig(saved);
      setEditorForm(buildEditableForm(saved));
      setLoadedConfigName(saved.identity.config_name);
      await refreshConfigsAndSelection(saved.identity.config_name);
      setSuccessMessage(`Saved ${saved.identity.config_name}.`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unknown error");
    } finally {
      setIsSavingConfig(false);
    }
  }

  async function handleSaveAsNewConfig() {
    if (!editorForm || !selectedConfig) return;
    try {
      setIsSavingConfig(true);
      setError(null);
      setSuccessMessage(null);
      const saved = await saveConfigAsNew(serializeEditorForm(editorForm, selectedConfig.recent_usage));
      setSelectedConfig(saved);
      setEditorForm(buildEditableForm(saved));
      setLoadedConfigName(saved.identity.config_name);
      await refreshConfigsAndSelection(saved.identity.config_name);
      setSuccessMessage(`Saved as new config ${saved.identity.config_name}.`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unknown error");
    } finally {
      setIsSavingConfig(false);
    }
  }

  function resetEditorToLoadedState() {
    if (!selectedConfig) return;
    setEditorForm(buildEditableForm(selectedConfig));
    setError(null);
    setSuccessMessage("Reverted unsaved edits to the last loaded canonical state.");
  }

  return (
    <div className="page-grid">
      <div className="panel hero-panel">
        <p className="eyebrow">Configs</p>
        <h1>Canonical run config browser and editor</h1>
        <p className="muted">
          Browse and edit the real runtime configs stored under <code>configs/runs</code>.
          This surface owns canonical experiment definition only, separate from template
          picking, presets, parallel workers, and launch orchestration.
        </p>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {successMessage ? <div className="success-banner">{successMessage}</div> : null}

      <div className="configs-layout">
        <aside className="panel configs-sidebar">
          <div className="results-panel-header">
            <div>
              <p className="eyebrow">Browser</p>
              <h2>Configs</h2>
            </div>
            <span className="muted">{`${filteredConfigs.length} visible`}</span>
          </div>

          <div className="configs-filter-grid">
            <label className="form-field">
              <span className="form-label">Search</span>
              <input type="search" placeholder="Name, dataset, stack..." value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} />
            </label>
            <label className="form-field">
              <span className="form-label">Dataset</span>
              <select value={selectedDataset} onChange={(event) => setSelectedDataset(event.target.value)}>
                {datasetOptions.map((option) => <option key={option} value={option}>{option === "all" ? "All datasets" : option}</option>)}
              </select>
            </label>
            <label className="form-field">
              <span className="form-label">Signal pack</span>
              <select value={selectedSignalPack} onChange={(event) => setSelectedSignalPack(event.target.value)}>
                {signalPackOptions.map((option) => <option key={option} value={option}>{option === "all" ? "All signal packs" : option}</option>)}
              </select>
            </label>
            <label className="form-field">
              <span className="form-label">Genome schema</span>
              <select value={selectedGenomeSchema} onChange={(event) => setSelectedGenomeSchema(event.target.value)}>
                {genomeSchemaOptions.map((option) => <option key={option} value={option}>{option === "all" ? "All genome schemas" : option}</option>)}
              </select>
            </label>
            <label className="form-field">
              <span className="form-label">Decision policy</span>
              <select value={selectedDecisionPolicy} onChange={(event) => setSelectedDecisionPolicy(event.target.value)}>
                {decisionPolicyOptions.map((option) => <option key={option} value={option}>{option === "all" ? "All decision policies" : option}</option>)}
              </select>
            </label>
            <label className="form-field">
              <span className="form-label">Mutation profile</span>
              <select value={selectedMutationProfile} onChange={(event) => setSelectedMutationProfile(event.target.value)}>
                {mutationProfileOptions.map((option) => <option key={option} value={option}>{option === "all" ? "All mutation profiles" : option}</option>)}
              </select>
            </label>
          </div>

          {isLoadingList ? <p className="loading-text">Loading canonical configs...</p> : filteredConfigs.length === 0 ? (
            <p className="muted">No canonical configs match the current filter.</p>
          ) : (
            <div className="config-row-list">
              {filteredConfigs.map((item) => {
                const isSelected = selectedConfigName === item.config_name;
                return (
                  <div key={item.config_name} className={isSelected ? "config-row-card selected" : "config-row-card"}>
                    <button className="config-row-main" onClick={() => onOpenConfig(item.config_name)} type="button">
                      <div className="config-row-header">
                        <strong className="primary-label">{item.config_name}</strong>
                        <span className="technical-meta-label">{item.generations_planned} generations</span>
                      </div>
                      <div className="campaign-card-meta">
                        <span>{item.dataset_catalog_id}</span>
                        <span>{item.signal_pack_name}</span>
                        <span>{item.genome_schema_name}</span>
                        <span>{item.decision_policy_name}</span>
                      </div>
                      <div className="campaign-card-meta">
                        <span>{item.mutation_profile_name}</span>
                        <span>{`${item.market_mode_name} x${item.leverage}`}</span>
                        <span>{item.seed_summary}</span>
                      </div>
                      <div className="campaign-card-meta">
                        <span>{`${item.recent_usage.campaign_usage_count} recent campaign uses`}</span>
                        <span>{item.recent_usage.latest_campaign_id ? `Last: ${formatDateTime(item.recent_usage.latest_campaign_started_at)}` : "Never executed"}</span>
                      </div>
                    </button>
                    <div className="config-row-actions">
                      <button className="subtle-inline-action-button" onClick={() => onOpenConfig(item.config_name)} type="button">Open</button>
                      <button className="subtle-inline-action-button" onClick={() => beginOperation({ kind: "duplicate", sourceConfigName: item.config_name })} type="button">Duplicate</button>
                      <button className="subtle-inline-action-button" onClick={() => beginOperation({ kind: "rename", sourceConfigName: item.config_name })} type="button">Rename</button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </aside>

        <section className="panel detail-panel">
          {!selectedConfigName ? <ConfigEmptyState /> : isLoadingDetail ? (
            <p className="loading-text">Loading normalized config editor...</p>
          ) : !selectedConfig || !editorForm ? (
            <ConfigUnavailableState />
          ) : (
            <ConfigEditorView
              editorForm={editorForm}
              isDirty={isDirty}
              isSavingConfig={isSavingConfig}
              loadedConfigName={loadedConfigName}
              selectedConfig={selectedConfig}
              onSave={() => void handleSaveCurrentConfig()}
              onSaveAsNew={() => void handleSaveAsNewConfig()}
              onReset={resetEditorToLoadedState}
              onUpdate={updateEditorForm}
            />
          )}
        </section>
      </div>

      {operation ? (
        <div className="modal-backdrop">
          <div className="modal-panel config-operation-modal">
            <div className="results-panel-header">
              <div>
                <p className="eyebrow">Config operation</p>
                <h2>{operation.kind === "duplicate" ? "Duplicate config" : "Rename config"}</h2>
              </div>
            </div>
            <p className="muted">Source config: <code>{operation.sourceConfigName}</code></p>
            <label className="form-field">
              <span className="form-label">{operation.kind === "duplicate" ? "New config name" : "Renamed config name"}</span>
              <input type="text" value={operationName} onChange={(event) => setOperationName(event.target.value)} placeholder="canonical_config_name" />
            </label>
            <div className="nav-actions">
              <button className="link-button secondary" onClick={closeOperation} type="button">Cancel</button>
              <button className="link-button" onClick={() => void submitOperation()} disabled={isSubmittingOperation || !operationName.trim()} type="button">
                {isSubmittingOperation ? "Saving..." : operation.kind === "duplicate" ? "Duplicate config" : "Rename config"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ConfigEmptyState() {
  return (
    <>
      <p className="eyebrow">Config editor</p>
      <h2>Select a canonical config</h2>
      <p className="muted">
        Choose a config from the browser to edit the explicit runtime experiment
        definition. Launch settings remain in Run Lab and are intentionally absent here.
      </p>
    </>
  );
}

function ConfigUnavailableState() {
  return (
    <>
      <p className="eyebrow">Config editor</p>
      <h2>Config not available</h2>
      <p className="muted">
        The selected config could not be loaded from the canonical config directory.
      </p>
    </>
  );
}

type ConfigEditorViewProps = {
  editorForm: EditableConfigForm;
  selectedConfig: RunConfigEditorView;
  loadedConfigName: string | null;
  isDirty: boolean;
  isSavingConfig: boolean;
  onSave: () => void;
  onSaveAsNew: () => void;
  onReset: () => void;
  onUpdate: (updater: (current: EditableConfigForm) => EditableConfigForm) => void;
};

function ConfigEditorView({
  editorForm,
  selectedConfig,
  loadedConfigName,
  isDirty,
  isSavingConfig,
  onSave,
  onSaveAsNew,
  onReset,
  onUpdate,
}: ConfigEditorViewProps) {
  const numericEvolutionFields = [
    ["mutation_seed", "Mutation seed"],
    ["population_size", "Population size"],
    ["target_population_size", "Target population"],
    ["survivors_count", "Survivors count"],
    ["generations_planned", "Generations planned"],
  ] as const;
  const tradingFields = [
    ["trade_cost_rate", "Trade cost rate", "0.0005"],
    ["cost_penalty_weight", "Cost penalty weight", "0.001"],
    ["trade_count_penalty_weight", "Trade count penalty", "0.001"],
    ["entry_score_margin", "Entry score margin", "0.001"],
    ["min_bars_between_entries", "Min bars between entries", "1"],
    ["entry_confirmation_bars", "Entry confirmation bars", "1"],
    ["min_trend_long_for_entry", "Min trend long", "0.001"],
    ["min_breakout_for_entry", "Min breakout", "0.001"],
    ["max_realized_volatility_for_entry", "Max realized volatility", "0.001"],
  ] as const;
  const jsonFields = [
    ["mutation_profile", "Mutation profile payload"],
    ["entry_trigger", "Entry trigger overrides"],
    ["exit_policy", "Exit policy overrides"],
    ["trade_control", "Trade control overrides"],
    ["entry_trigger_constraints", "Entry trigger constraints"],
  ] as const;

  return (
    <>
      <div className="results-panel-header">
        <div>
          <p className="eyebrow">Config editor</p>
          <h2>{loadedConfigName}</h2>
        </div>
        <span className="muted">{editorForm.identity.config_path}</span>
      </div>

      <div className="config-editor-toolbar">
        <span className={isDirty ? "config-dirty-badge dirty" : "config-dirty-badge"}>
          {isDirty ? "Unsaved changes" : "Saved state"}
        </span>
        <div className="nav-actions">
          <button className="link-button secondary" onClick={onReset} disabled={!isDirty || isSavingConfig} type="button">Reset</button>
          <button className="link-button secondary" onClick={onSaveAsNew} disabled={isSavingConfig} type="button">
            {isSavingConfig ? "Saving..." : "Save as new"}
          </button>
          <button className="link-button" onClick={onSave} disabled={isSavingConfig} type="button">
            {isSavingConfig ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      <div className="config-editor-sections">
        <div className="review-card config-editor-section">
          <div className="config-editor-section-header">
            <div>
              <p className="eyebrow">Identity</p>
              <h3>Canonical file identity</h3>
            </div>
            <span className="muted">Use Save as new for new file names.</span>
          </div>
          <div className="inline-fields">
            <label className="form-field">
              <span className="form-label">Config name</span>
              <input type="text" value={editorForm.identity.config_name} onChange={(event) => onUpdate((current) => ({ ...current, identity: { ...current.identity, config_name: event.target.value } }))} />
            </label>
            <label className="form-field">
              <span className="form-label">Canonical path</span>
              <input type="text" value={editorForm.identity.config_path} disabled />
            </label>
          </div>
        </div>

        <div className="review-card config-editor-section">
          <div className="config-editor-section-header">
            <div>
              <p className="eyebrow">Research stack</p>
              <h3>Experiment components</h3>
            </div>
          </div>
          <div className="inline-fields config-editor-grid-3">
            {([
              ["dataset_catalog_id", "Dataset catalog"],
              ["signal_pack_name", "Signal pack"],
              ["genome_schema_name", "Genome schema"],
              ["decision_policy_name", "Decision policy"],
              ["mutation_profile_name", "Mutation profile"],
              ["market_mode_name", "Market mode"],
              ["leverage", "Leverage"],
            ] as const).map(([field, label]) => (
              <label key={field} className="form-field">
                <span className="form-label">{label}</span>
                <input
                  type={field === "leverage" ? "number" : "text"}
                  step={field === "leverage" ? "0.01" : undefined}
                  value={editorForm.research_stack[field]}
                  onChange={(event) =>
                    onUpdate((current) => ({
                      ...current,
                      research_stack: { ...current.research_stack, [field]: event.target.value },
                    }))
                  }
                />
              </label>
            ))}
          </div>
        </div>

        <div className="review-card config-editor-section">
          <div className="config-editor-section-header">
            <div>
              <p className="eyebrow">Evolution budget</p>
              <h3>Search budget and mutation seed</h3>
            </div>
          </div>
          <div className="inline-fields config-editor-grid-5">
            {numericEvolutionFields.map(([field, label]) => (
              <label key={field} className="form-field">
                <span className="form-label">{label}</span>
                <input
                  type="number"
                  value={editorForm.evolution_budget[field]}
                  onChange={(event) =>
                    onUpdate((current) => ({
                      ...current,
                      evolution_budget: { ...current.evolution_budget, [field]: event.target.value },
                    }))
                  }
                />
              </label>
            ))}
          </div>
        </div>

        <div className="review-card config-editor-section">
          <div className="config-editor-section-header">
            <div>
              <p className="eyebrow">Seed plan</p>
              <h3>Explicit or range-based seed definition</h3>
            </div>
          </div>
          <div className="mode-toggle-row">
            {[
              ["range", "Range mode"],
              ["explicit", "Explicit seeds"],
              ["runtime_default", "Runtime default"],
            ].map(([id, label]) => (
              <button
                key={id}
                className={editorForm.seed_plan.mode === id ? "link-button active-toggle" : "link-button secondary"}
                onClick={() => onUpdate((current) => ({ ...current, seed_plan: { ...current.seed_plan, mode: id } }))}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
          {editorForm.seed_plan.mode === "range" ? (
            <div className="inline-fields">
              <label className="form-field">
                <span className="form-label">Seed start</span>
                <input type="number" value={editorForm.seed_plan.seed_start} onChange={(event) => onUpdate((current) => ({ ...current, seed_plan: { ...current.seed_plan, seed_start: event.target.value } }))} />
              </label>
              <label className="form-field">
                <span className="form-label">Seed count</span>
                <input type="number" value={editorForm.seed_plan.seed_count} onChange={(event) => onUpdate((current) => ({ ...current, seed_plan: { ...current.seed_plan, seed_count: event.target.value } }))} />
              </label>
            </div>
          ) : null}
          {editorForm.seed_plan.mode === "explicit" ? (
            <label className="form-field">
              <span className="form-label">Explicit seeds</span>
              <input type="text" value={editorForm.seed_plan.explicit_seeds} onChange={(event) => onUpdate((current) => ({ ...current, seed_plan: { ...current.seed_plan, explicit_seeds: event.target.value } }))} placeholder="100, 101, 102" />
            </label>
          ) : null}
          <p className="muted config-inline-note">
            {editorForm.seed_plan.mode === "explicit"
              ? "Explicit seed mode is active. This editor never mixes explicit seeds with seed ranges."
              : editorForm.seed_plan.mode === "range"
                ? "Range seed mode is active. This editor keeps seed_start and seed_count explicit."
                : "Runtime default seed mode is active. No explicit seed values will be written."}
          </p>
        </div>

        <div className="review-card config-editor-section">
          <div className="config-editor-section-header">
            <div>
              <p className="eyebrow">Evaluation &amp; trading</p>
              <h3>Runtime scoring and trading knobs</h3>
            </div>
          </div>
          <div className="inline-fields config-editor-grid-3">
            {tradingFields.map(([field, label, step]) => (
              <label key={field} className="form-field">
                <span className="form-label">{label}</span>
                <input
                  type="number"
                  step={step}
                  value={editorForm.evaluation_trading[field]}
                  onChange={(event) =>
                    onUpdate((current) => ({
                      ...current,
                      evaluation_trading: { ...current.evaluation_trading, [field]: event.target.value },
                    }))
                  }
                />
              </label>
            ))}
            <label className="form-field">
              <span className="form-label">Regime filter enabled</span>
              <label className="module-required-toggle">
                <input
                  type="checkbox"
                  checked={editorForm.evaluation_trading.regime_filter_enabled}
                  onChange={(event) =>
                    onUpdate((current) => ({
                      ...current,
                      evaluation_trading: { ...current.evaluation_trading, regime_filter_enabled: event.target.checked },
                    }))
                  }
                />
                <span>{editorForm.evaluation_trading.regime_filter_enabled ? "Enabled" : "Disabled"}</span>
              </label>
            </label>
          </div>
        </div>

        <div className="review-card config-editor-section">
          <div className="config-editor-section-header">
            <div>
              <p className="eyebrow">Advanced structured overrides</p>
              <h3>Explicit JSON payloads used by runtime</h3>
            </div>
            <span className="muted">These remain visible and editable on purpose.</span>
          </div>
          <div className="config-json-grid">
            {jsonFields.map(([field, label]) => (
              <label key={field} className="form-field">
                <span className="form-label">{label}</span>
                <textarea
                  rows={8}
                  value={editorForm.advanced_overrides[field]}
                  onChange={(event) =>
                    onUpdate((current) => ({
                      ...current,
                      advanced_overrides: { ...current.advanced_overrides, [field]: event.target.value },
                    }))
                  }
                />
              </label>
            ))}
          </div>
        </div>

        <div className="review-card config-editor-section">
          <div className="config-editor-section-header">
            <div>
              <p className="eyebrow">Recent usage</p>
              <h3>Persistence-derived context</h3>
            </div>
          </div>
          <dl className="compact-grid">
            <dt>Campaign usage count</dt>
            <dd>{selectedConfig.recent_usage.campaign_usage_count}</dd>
            <dt>Latest campaign</dt>
            <dd>{selectedConfig.recent_usage.latest_campaign_id ?? "No persisted campaign usage"}</dd>
            <dt>Latest started at</dt>
            <dd>{formatDateTime(selectedConfig.recent_usage.latest_campaign_started_at)}</dd>
            <dt>Latest status</dt>
            <dd>{formatStatus(selectedConfig.recent_usage.latest_campaign_status)}</dd>
            <dt>Persisted executions</dt>
            <dd>{selectedConfig.recent_usage.appears_in_persisted_executions ? "Yes" : "No"}</dd>
          </dl>
        </div>
      </div>
    </>
  );
}
