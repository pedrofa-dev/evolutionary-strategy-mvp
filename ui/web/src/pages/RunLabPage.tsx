import { useEffect, useMemo, useState } from "react";

import MutationProfileModal from "../components/MutationProfileModal";
import SignalPackModal from "../components/SignalPackModal";
import { getDisplayLabel } from "../content/catalogMetadata";
import { getRunLabBootstrap, saveAndExecuteRun, saveRunConfig } from "../services/runLabApi";
import type {
  LaunchedRunResult,
  RunLabBootstrap,
  RunLabDatasetCatalogSummary,
  RunLabOption,
  RunLabSaveRequest,
  SavedSignalPackAssetResult,
  RunLabTemplateSummary,
  SavedMutationProfileAssetResult,
  SavedRunConfigResult,
} from "../types/runLab";

type RunLabPageProps = {
  onOpenCatalog: () => void;
  onOpenResults: (campaignId?: string | null) => void;
};

type ActionState = "idle" | "saving" | "executing";
type ConfigMode = "existing" | "new";
const RESULTS_PREFERRED_CONFIG_KEY = "results-preferred-config-name";
const RESULTS_PREFERRED_LAUNCH_AT_KEY = "results-preferred-launch-at";
const RESULTS_NAVIGATION_INTENT_KEY = "results-navigation-intent";

type FormState = {
  config_mode: ConfigMode;
  template_config_name: string;
  config_name: string;
  dataset_catalog_id: string;
  signal_pack_name: string;
  genome_schema_name: string;
  mutation_profile_name: string;
  decision_policy_name: string;
  experiment_preset_name: string;
  parallel_workers: string;
  queue_concurrency_limit: string;
  seed_mode: "range" | "explicit";
  seed_start: string;
  seed_count: string;
  explicit_seeds: string;
};

function buildFormStateFromTemplate(
  template: RunLabTemplateSummary,
  bootstrap: RunLabBootstrap,
  options?: {
    previous?: FormState | null;
    configMode?: ConfigMode;
    configName?: string;
  },
): FormState {
  const previous = options?.previous ?? null;
  const configMode = options?.configMode ?? previous?.config_mode ?? "new";

  return {
    config_mode: configMode,
    template_config_name: template.id,
    config_name:
      options?.configName ??
      (configMode === "existing" ? template.id : previous?.config_name ?? ""),
    dataset_catalog_id: template.dataset_catalog_id,
    signal_pack_name: template.signal_pack_name,
    genome_schema_name: template.genome_schema_name,
    mutation_profile_name: template.mutation_profile_name,
    decision_policy_name: template.decision_policy_name,
    experiment_preset_name:
      previous?.experiment_preset_name ?? bootstrap.defaults.experiment_preset_name,
    parallel_workers:
      previous?.parallel_workers ?? bootstrap.defaults.parallel_workers.toString(),
    queue_concurrency_limit:
      previous?.queue_concurrency_limit ??
      bootstrap.defaults.queue_concurrency_limit.toString(),
    seed_mode: template.seed_mode,
    seed_start: template.seed_start?.toString() ?? "",
    seed_count: template.seed_count?.toString() ?? "",
    explicit_seeds: template.explicit_seeds.join(", "),
  };
}

function buildInitialFormState(bootstrap: RunLabBootstrap): FormState {
  const initialTemplate =
    bootstrap.config_templates.find(
      (template) => template.id === bootstrap.defaults.template_config_name,
    ) ?? bootstrap.config_templates[0];

  return buildFormStateFromTemplate(initialTemplate, bootstrap, {
    configMode: "new",
  });
}

function buildSavePayload(form: FormState): RunLabSaveRequest {
  return {
    template_config_name: form.template_config_name,
    config_name: form.config_name,
    dataset_catalog_id: form.dataset_catalog_id,
    signal_pack_name: form.signal_pack_name,
    genome_schema_name: form.genome_schema_name,
    mutation_profile_name: form.mutation_profile_name,
    decision_policy_name: form.decision_policy_name,
    seed_mode: form.seed_mode,
    seed_start: form.seed_mode === "range" && form.seed_start ? Number(form.seed_start) : null,
    seed_count: form.seed_mode === "range" && form.seed_count ? Number(form.seed_count) : null,
    explicit_seeds: form.seed_mode === "explicit" ? form.explicit_seeds : "",
    parallel_workers: form.parallel_workers ? Number(form.parallel_workers) : 1,
    queue_concurrency_limit: form.queue_concurrency_limit
      ? Number(form.queue_concurrency_limit)
      : 1,
  };
}

function findOption(options: RunLabOption[], id: string): RunLabOption | null {
  return options.find((option) => option.id === id) ?? null;
}

function findDataset(
  datasetCatalogs: RunLabDatasetCatalogSummary[],
  id: string,
): RunLabDatasetCatalogSummary | null {
  return datasetCatalogs.find((item) => item.id === id) ?? null;
}

function findTemplate(
  templates: RunLabTemplateSummary[],
  id: string,
): RunLabTemplateSummary | null {
  return templates.find((item) => item.id === id) ?? null;
}

function renderSplitSummary(summary: Record<string, number>): string {
  return Object.entries(summary)
    .map(([layer, count]) => `${layer}: ${count}`)
    .join(" | ");
}

function duplicateConfigName(templateId: string): string {
  return templateId.replace(/\.json$/i, " copy");
}

function applyBootstrapSelection(
  nextBootstrap: RunLabBootstrap,
  options?: {
    currentForm?: FormState | null;
    preferredSignalPackId?: string | null;
    preferredMutationProfileId?: string | null;
  },
): FormState {
  const currentForm = options?.currentForm ?? null;
  const baseForm = currentForm
    ? buildFormStateFromTemplate(
        nextBootstrap.config_templates.find(
          (template) => template.id === currentForm.template_config_name,
        ) ?? nextBootstrap.config_templates[0],
        nextBootstrap,
        {
          previous: currentForm,
          configMode: currentForm.config_mode,
          configName: currentForm.config_name,
        },
      )
    : buildInitialFormState(nextBootstrap);

  if (
    options?.preferredSignalPackId &&
    nextBootstrap.signal_packs.some(
      (option) => option.id === options.preferredSignalPackId && option.selectable,
    )
  ) {
    return {
      ...baseForm,
      signal_pack_name: options.preferredSignalPackId,
    };
  }

  if (
    options?.preferredMutationProfileId &&
    nextBootstrap.mutation_profiles.some(
      (option) => option.id === options.preferredMutationProfileId && option.selectable,
    )
  ) {
    return {
      ...baseForm,
      mutation_profile_name: options.preferredMutationProfileId,
    };
  }

  return baseForm;
}

function openContextualResults(
  onOpenResults: (campaignId?: string | null) => void,
  campaignId?: string | null,
) {
  window.sessionStorage.setItem(RESULTS_NAVIGATION_INTENT_KEY, "run-lab");
  onOpenResults(campaignId);
}

export default function RunLabPage({ onOpenCatalog, onOpenResults }: RunLabPageProps) {
  const [bootstrap, setBootstrap] = useState<RunLabBootstrap | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [advancedMode, setAdvancedMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [actionState, setActionState] = useState<ActionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [savedResult, setSavedResult] = useState<SavedRunConfigResult | null>(null);
  const [launchResult, setLaunchResult] = useState<LaunchedRunResult | null>(null);
  const [isSignalPackModalOpen, setIsSignalPackModalOpen] = useState(false);
  const [isMutationProfileModalOpen, setIsMutationProfileModalOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadBootstrap() {
      try {
        setIsLoading(true);
        setError(null);
        setBootstrap(null);
        setForm(null);
        const nextBootstrap = await getRunLabBootstrap();
        if (!cancelled) {
          setBootstrap(nextBootstrap);
          setForm(applyBootstrapSelection(nextBootstrap));
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadBootstrap();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function refreshBootstrap(
    preferredSignalPackId?: string | null,
    preferredMutationProfileId?: string | null,
    currentFormOverride?: FormState | null,
  ) {
    const nextBootstrap = await getRunLabBootstrap();
    setBootstrap(nextBootstrap);
    setForm(
      applyBootstrapSelection(nextBootstrap, {
        currentForm: currentFormOverride ?? form,
        preferredSignalPackId,
        preferredMutationProfileId,
      }),
    );
  }

  const selectedDataset = useMemo(
    () => (bootstrap && form ? findDataset(bootstrap.dataset_catalogs, form.dataset_catalog_id) : null),
    [bootstrap, form],
  );
  const selectedSignalPack = useMemo(
    () => (bootstrap && form ? findOption(bootstrap.signal_packs, form.signal_pack_name) : null),
    [bootstrap, form],
  );
  const selectedGenomeSchema = useMemo(
    () => (bootstrap && form ? findOption(bootstrap.genome_schemas, form.genome_schema_name) : null),
    [bootstrap, form],
  );
  const selectedMutationProfile = useMemo(
    () => (bootstrap && form ? findOption(bootstrap.mutation_profiles, form.mutation_profile_name) : null),
    [bootstrap, form],
  );
  const selectedDecisionPolicy = useMemo(
    () => (bootstrap && form ? findOption(bootstrap.decision_policies, form.decision_policy_name) : null),
    [bootstrap, form],
  );
  const selectedExecutionPreset = useMemo(
    () => (bootstrap && form ? findOption(bootstrap.execution_presets, form.experiment_preset_name) : null),
    [bootstrap, form],
  );
  const selectedTemplate = useMemo(
    () => (bootstrap && form ? findTemplate(bootstrap.config_templates, form.template_config_name) : null),
    [bootstrap, form],
  );
  const isExistingConfigMode = form?.config_mode === "existing";

  const selectableSignalPacks = useMemo(
    () => bootstrap?.signal_packs.filter((option) => option.selectable) ?? [],
    [bootstrap],
  );
  const selectableGenomeSchemas = useMemo(
    () => bootstrap?.genome_schemas.filter((option) => option.selectable) ?? [],
    [bootstrap],
  );
  const selectableMutationProfiles = useMemo(
    () => bootstrap?.mutation_profiles.filter((option) => option.selectable) ?? [],
    [bootstrap],
  );
  const selectableDecisionPolicies = useMemo(
    () => bootstrap?.decision_policies.filter((option) => option.selectable) ?? [],
    [bootstrap],
  );

  const reviewWarnings = useMemo(() => {
    const warnings: string[] = [];

    if (!selectedDataset) {
      warnings.push("A dataset catalog is required.");
    }
    if (!selectedSignalPack || !selectedGenomeSchema || !selectedMutationProfile || !selectedDecisionPolicy) {
      warnings.push("Signal pack, genome schema, mutation profile, and decision policy are all required.");
    }
    if (!form?.config_name.trim()) {
      warnings.push("Run config name is required before saving.");
    }
    for (const option of [
      selectedSignalPack,
      selectedGenomeSchema,
      selectedMutationProfile,
      selectedDecisionPolicy,
    ]) {
      if (option?.warning) {
        warnings.push(option.warning);
      }
    }
    if (form?.seed_mode === "range" && (!form.seed_start || !form.seed_count)) {
      warnings.push("Range seed mode requires both seed start and seed count.");
    }
    if (form?.seed_mode === "explicit" && !form.explicit_seeds.trim()) {
      warnings.push("Explicit seed mode requires at least one seed.");
    }
    if (!form?.parallel_workers || Number(form.parallel_workers) <= 0) {
      warnings.push("Parallel workers inside one run must be greater than 0.");
    }
    if (!form?.queue_concurrency_limit || Number(form.queue_concurrency_limit) <= 0) {
      warnings.push("Queue concurrency limit must be greater than 0.");
    }
    return warnings;
  }, [
    form,
    selectedDataset,
    selectedSignalPack,
    selectedGenomeSchema,
    selectedMutationProfile,
    selectedDecisionPolicy,
  ]);

  const hasBlockingReviewIssue = useMemo(() => {
    if (!selectedDataset || !selectedSignalPack || !selectedGenomeSchema || !selectedMutationProfile || !selectedDecisionPolicy) {
      return true;
    }
    if (!form?.config_name.trim()) {
      return true;
    }
    if (form.seed_mode === "range") {
      if (!form.parallel_workers || Number(form.parallel_workers) <= 0) {
        return true;
      }
      if (!form.queue_concurrency_limit || Number(form.queue_concurrency_limit) <= 0) {
        return true;
      }
      return !form.seed_start || !form.seed_count;
    }
    if (!form.parallel_workers || Number(form.parallel_workers) <= 0) {
      return true;
    }
    if (!form.queue_concurrency_limit || Number(form.queue_concurrency_limit) <= 0) {
      return true;
    }
    return !form.explicit_seeds.trim();
  }, [
    form,
    selectedDataset,
    selectedSignalPack,
    selectedGenomeSchema,
    selectedMutationProfile,
    selectedDecisionPolicy,
  ]);

  async function handleSave() {
    if (!form) {
      return;
    }
    try {
      setActionState("saving");
      setError(null);
      setLaunchResult(null);
      const result = await saveRunConfig(buildSavePayload(form));
      setSavedResult(result);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unknown error");
    } finally {
      setActionState("idle");
    }
  }

  async function handleSaveAndExecute() {
    if (!form) {
      return;
    }
    try {
      setActionState("executing");
      setError(null);
      const result = await saveAndExecuteRun({
        ...buildSavePayload(form),
        experiment_preset_name: form.experiment_preset_name || null,
      });
      window.sessionStorage.setItem(
        RESULTS_PREFERRED_CONFIG_KEY,
        result.saved_config.config_name,
      );
      window.sessionStorage.setItem(
        RESULTS_PREFERRED_LAUNCH_AT_KEY,
        new Date().toISOString(),
      );
      setSavedResult(result.saved_config);
      setLaunchResult(result);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unknown error");
    } finally {
      setActionState("idle");
    }
  }

  function handleConfigModeChange(nextMode: ConfigMode) {
    if (!bootstrap || !form || form.config_mode === nextMode) {
      return;
    }

    const template =
      findTemplate(bootstrap.config_templates, form.template_config_name) ??
      bootstrap.config_templates[0];

    setForm(
      buildFormStateFromTemplate(template, bootstrap, {
        previous: form,
        configMode: nextMode,
        configName:
          nextMode === "existing"
            ? template.id
            : form.config_name.trim() && form.config_name !== template.id
              ? form.config_name
              : duplicateConfigName(template.id),
      }),
    );
  }

  async function handleMutationProfileSaved(
    result: SavedMutationProfileAssetResult,
  ) {
    const nextForm =
      form?.config_mode === "existing" && form
        ? {
            ...form,
            config_mode: "new" as const,
            config_name:
              form.config_name.trim() && form.config_name !== form.template_config_name
                ? form.config_name
                : duplicateConfigName(form.template_config_name),
          }
        : form;
    await refreshBootstrap(null, result.asset_id, nextForm);
    setIsMutationProfileModalOpen(false);
  }

  async function handleSignalPackSaved(
    result: SavedSignalPackAssetResult,
  ) {
    const nextForm =
      form?.config_mode === "existing" && form
        ? {
            ...form,
            config_mode: "new" as const,
            config_name:
              form.config_name.trim() && form.config_name !== form.template_config_name
                ? form.config_name
                : duplicateConfigName(form.template_config_name),
          }
        : form;
    await refreshBootstrap(result.asset_id, null, nextForm);
    setIsSignalPackModalOpen(false);
  }

  if (isLoading) {
    return (
      <div className="page-grid">
        <div className="panel hero-panel">
          <p className="eyebrow">Run Lab</p>
          <h1>Prepare and launch a canonical multiseed run</h1>
          <p className="loading-text">Loading Run Lab bootstrap...</p>
        </div>
      </div>
    );
  }

  if (error || !bootstrap || !form) {
    return (
      <div className="page-grid">
        <div className="panel hero-panel">
          <p className="eyebrow">Run Lab</p>
          <h1>Prepare and launch a canonical run</h1>
          <p className="muted">Run Lab bootstrap failed.</p>
          <div className="error-banner">
            {error ?? "Run Lab could not load its bootstrap data."}
          </div>
          <div className="nav-actions">
            <button
              className="link-button"
              onClick={() => setReloadKey((current) => current + 1)}
              type="button"
            >
              Retry bootstrap
            </button>
            <button className="link-button secondary" onClick={onOpenCatalog} type="button">
              Back to catalog
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-grid">
      <div className="panel hero-panel">
        <p className="eyebrow">Run Lab</p>
        <h1>Prepare and launch a canonical run</h1>
        <p className="muted">
          This flow saves a canonical config under <code>configs/runs/</code> and
          submits it into the persisted local execution queue that launches the
          existing multiseed entrypoint.
        </p>
        <div className="nav-actions">
          <button
            className="link-button secondary"
            onClick={() => setAdvancedMode((current) => !current)}
            type="button"
          >
            {advancedMode ? "Hide advanced controls" : "Show advanced controls"}
          </button>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      {savedResult ? (
        <div className="panel">
          <h2>Config saved</h2>
          <p className="muted">
            Saved as <code>{savedResult.config_path}</code>
          </p>
        </div>
      ) : null}

      {launchResult ? (
        <div className="panel">
          <h2>Execution submitted</h2>
          <p className="muted">
            Job <strong>{launchResult.job_id}</strong> is currently{" "}
            <strong>{launchResult.status}</strong> with preset{" "}
            <strong>{launchResult.preset_name ?? "none"}</strong>.
          </p>
          <div className="technical-meta">
            <span className="technical-meta-label">Launch metadata</span>
            <code>
              campaign: {launchResult.campaign_id}
              {"\n"}
              config set: {launchResult.execution_configs_dir}
              {"\n"}
              log: {launchResult.launch_log_path}
              {"\n"}
              pid: {launchResult.pid ?? "not started yet"}
            </code>
          </div>
          <div className="nav-actions">
            <button
              className="link-button secondary"
              onClick={() =>
                openContextualResults(
                  onOpenResults,
                  launchResult.status === "queued" ? null : launchResult.campaign_id,
                )
              }
              type="button"
            >
              View results
            </button>
          </div>
        </div>
      ) : null}

      <div className="page-grid run-lab-grid">
        <div className="panel">
          <h2>1. Dataset</h2>
          <label className="form-field">
            <span className="form-label">Dataset catalog</span>
            <select
              value={form.dataset_catalog_id}
              disabled={isExistingConfigMode}
              onChange={(event) =>
                setForm((current) =>
                  current
                    ? {
                        ...current,
                        dataset_catalog_id: event.target.value,
                      }
                    : current,
                )
              }
            >
              {bootstrap.dataset_catalogs.map((catalog) => (
                <option key={catalog.id} value={catalog.id}>
                  {getDisplayLabel(catalog.id)} ({catalog.timeframe})
                </option>
              ))}
            </select>
          </label>

          {selectedDataset ? (
            <div className="review-card">
              <strong className="primary-label">{getDisplayLabel(selectedDataset.id)}</strong>
              <div className="item-card-id">{selectedDataset.id}</div>
              <p className="muted">{selectedDataset.description}</p>
              <dl className="compact-grid">
                <dt>Market</dt>
                <dd>{selectedDataset.market_type}</dd>
                <dt>Assets</dt>
                <dd>{selectedDataset.asset_symbols.join(", ")}</dd>
                <dt>Timeframe</dt>
                <dd>{selectedDataset.timeframe}</dd>
                <dt>Date range</dt>
                <dd>
                  {`${selectedDataset.date_range_start} to ${selectedDataset.date_range_end}`}
                </dd>
                <dt>Splits</dt>
                <dd>{renderSplitSummary(selectedDataset.split_summary)}</dd>
              </dl>
              {advancedMode ? (
                <div className="technical-meta">
                  <span className="technical-meta-label">Dataset selection samples</span>
                  <code>{JSON.stringify(selectedDataset.sample_dataset_ids, null, 2)}</code>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="panel">
          <h2>2. Strategy Shape</h2>
          <label className="form-field">
            <span className="form-label form-label-row">
              <span>Signal pack</span>
              <button
                className="link-button secondary inline-action-button"
                onClick={() => setIsSignalPackModalOpen(true)}
                type="button"
              >
                New
              </button>
            </span>
            <select
              value={form.signal_pack_name}
              disabled={isExistingConfigMode}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, signal_pack_name: event.target.value } : current,
                )
              }
            >
              {selectableSignalPacks.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span className="form-label">Genome schema</span>
            <select
              value={form.genome_schema_name}
              disabled={isExistingConfigMode}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, genome_schema_name: event.target.value } : current,
                )
              }
            >
              {selectableGenomeSchemas.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span className="form-label form-label-row">
              <span>Mutation profile</span>
              <button
                className="link-button secondary inline-action-button"
                onClick={() => setIsMutationProfileModalOpen(true)}
                type="button"
              >
                New
              </button>
            </span>
            <select
              value={form.mutation_profile_name}
              disabled={isExistingConfigMode}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, mutation_profile_name: event.target.value } : current,
                )
              }
            >
              {selectableMutationProfiles.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {advancedMode ? (
            <div className="reference-list">
              <h3>Reference examples</h3>
              {[...bootstrap.signal_packs, ...bootstrap.genome_schemas, ...bootstrap.mutation_profiles]
                .filter((option) => !option.selectable)
                .map((option) => (
                  <div key={option.id} className="reference-item">
                    <strong>{option.label}</strong>
                    <span className="item-card-id">{option.id}</span>
                    <span className="muted">{option.warning}</span>
                  </div>
                ))}
            </div>
          ) : null}
        </div>

        <div className="panel">
          <h2>3. Decision Logic</h2>
          <label className="form-field">
            <span className="form-label">Decision policy</span>
            <select
              value={form.decision_policy_name}
              disabled={isExistingConfigMode}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, decision_policy_name: event.target.value } : current,
                )
              }
            >
              {selectableDecisionPolicies.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {selectedDecisionPolicy ? (
            <div className="review-card">
              <strong className="primary-label">{selectedDecisionPolicy.label}</strong>
              <div className="item-card-id">{selectedDecisionPolicy.id}</div>
              <p className="muted">
                {selectedDecisionPolicy.description ?? "No description available."}
              </p>
              <dl className="compact-grid">
                <dt>Main concept</dt>
                <dd>Decision policy</dd>
                <dt>Policy engine</dt>
                <dd>{selectedDecisionPolicy.engine_name ?? "Not exposed"}</dd>
              </dl>
            </div>
          ) : null}

          {advancedMode ? (
            <div className="reference-list">
              <h3>Reference policy assets</h3>
              {bootstrap.decision_policies
                .filter((option) => !option.selectable)
                .map((option) => (
                  <div key={option.id} className="reference-item">
                    <strong>{option.label}</strong>
                    <span className="item-card-id">{option.id}</span>
                    <span className="muted">{option.warning}</span>
                  </div>
                ))}
            </div>
          ) : null}
        </div>

        <div className="panel">
          <h2>4. Run Config</h2>
          <div className="mode-toggle-row">
            <button
              className={form.config_mode === "existing" ? "link-button active-toggle" : "link-button secondary"}
              onClick={() => handleConfigModeChange("existing")}
              type="button"
            >
              Use existing config
            </button>
            <button
              className={form.config_mode === "new" ? "link-button active-toggle" : "link-button secondary"}
              onClick={() => handleConfigModeChange("new")}
              type="button"
            >
              Create new config
            </button>
          </div>

          <label className="form-field">
            <span className="form-label">
              {isExistingConfigMode ? "Canonical config" : "Starting template"}
            </span>
            <select
              value={form.template_config_name}
              onChange={(event) => {
                const nextTemplate = findTemplate(
                  bootstrap.config_templates,
                  event.target.value,
                );
                setForm((current) =>
                  current && nextTemplate
                    ? buildFormStateFromTemplate(nextTemplate, bootstrap, {
                        previous: current,
                        configMode: current.config_mode,
                        configName:
                          current.config_mode === "existing"
                            ? nextTemplate.id
                            : current.config_name,
                      })
                    : current,
                );
              }}
            >
              {bootstrap.config_templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.label}
                </option>
              ))}
            </select>
          </label>

          <p className="muted">
            {isExistingConfigMode
              ? "Run Lab will reuse the selected canonical config. Strategy shape and seed structure stay locked to avoid accidental drift."
              : "Create a new canonical config, optionally starting from an existing template."}
          </p>

          <label className="form-field">
            <span className="form-label">Run config name</span>
            <input
              type="text"
              value={form.config_name}
              disabled={isExistingConfigMode}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, config_name: event.target.value } : current,
                )
              }
              placeholder="example: bnb run lab probe"
            />
          </label>

          <label className="form-field">
            <span className="form-label">Experiment preset</span>
            <select
              value={form.experiment_preset_name}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, experiment_preset_name: event.target.value } : current,
                )
              }
            >
              {bootstrap.execution_presets.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span className="form-label">Parallel workers inside run</span>
            <input
              type="number"
              min="1"
              value={form.parallel_workers}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, parallel_workers: event.target.value } : current,
                )
              }
            />
          </label>

          <label className="form-field">
            <span className="form-label">Queue concurrency limit</span>
            <input
              type="number"
              min="1"
              value={form.queue_concurrency_limit}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, queue_concurrency_limit: event.target.value } : current,
                )
              }
            />
          </label>

          <label className="form-field">
            <span className="form-label">Seed mode</span>
            <select
              value={form.seed_mode}
              disabled={isExistingConfigMode}
              onChange={(event) =>
                setForm((current) =>
                  current
                    ? {
                        ...current,
                        seed_mode: event.target.value as "range" | "explicit",
                      }
                    : current,
                )
              }
            >
              <option value="range">Range</option>
              <option value="explicit">Explicit list</option>
            </select>
          </label>

          {form.seed_mode === "range" ? (
            <div className="inline-fields">
              <label className="form-field">
                <span className="form-label">Seed start</span>
                <input
                  type="number"
                  value={form.seed_start}
                  disabled={isExistingConfigMode}
                  onChange={(event) =>
                    setForm((current) =>
                      current ? { ...current, seed_start: event.target.value } : current,
                    )
                  }
                />
              </label>
              <label className="form-field">
                <span className="form-label">Seed count</span>
                <input
                  type="number"
                  value={form.seed_count}
                  disabled={isExistingConfigMode}
                  onChange={(event) =>
                    setForm((current) =>
                      current ? { ...current, seed_count: event.target.value } : current,
                    )
                  }
                />
              </label>
            </div>
          ) : (
            <label className="form-field">
              <span className="form-label">Explicit seeds</span>
              <input
                type="text"
                value={form.explicit_seeds}
                disabled={isExistingConfigMode}
                onChange={(event) =>
                  setForm((current) =>
                    current ? { ...current, explicit_seeds: event.target.value } : current,
                  )
                }
                placeholder="101, 102, 103"
              />
            </label>
          )}

          {advancedMode ? (
            <>
              <div className="technical-meta">
                <span className="technical-meta-label">Canonical execution metadata</span>
                <code>
                  logic_version={bootstrap.current_logic_version}
                  {"\n"}
                  template={selectedTemplate?.file_path ?? "none"}
                </code>
              </div>
            </>
          ) : null}
        </div>
      </div>

      <div className="panel">
        <h2>5. Review</h2>
        <div className="review-grid">
          <div className="review-card review-selection-card">
            <span className="technical-meta-label">Dataset</span>
            <div className="review-card-heading">
              <strong className="primary-label">
                {selectedDataset ? getDisplayLabel(selectedDataset.id) : "Missing dataset"}
              </strong>
              <span className="item-card-id">{selectedDataset?.id ?? "none"}</span>
            </div>
          </div>
          <div className="review-card review-selection-card">
            <span className="technical-meta-label">Signal pack</span>
            <div className="review-card-heading">
              <strong className="primary-label">{selectedSignalPack?.label ?? "Missing"}</strong>
              <span className="item-card-id">{selectedSignalPack?.id ?? "none"}</span>
            </div>
          </div>
          <div className="review-card review-selection-card">
            <span className="technical-meta-label">Genome schema</span>
            <div className="review-card-heading">
              <strong className="primary-label">{selectedGenomeSchema?.label ?? "Missing"}</strong>
              <span className="item-card-id">{selectedGenomeSchema?.id ?? "none"}</span>
            </div>
          </div>
          <div className="review-card review-selection-card">
            <span className="technical-meta-label">Mutation profile</span>
            <div className="review-card-heading">
              <strong className="primary-label">{selectedMutationProfile?.label ?? "Missing"}</strong>
              <span className="item-card-id">{selectedMutationProfile?.id ?? "none"}</span>
            </div>
          </div>
          <div className="review-card review-selection-card">
            <span className="technical-meta-label">Decision policy</span>
            <div className="review-card-heading">
              <strong className="primary-label">{selectedDecisionPolicy?.label ?? "Missing"}</strong>
              <span className="item-card-id">{selectedDecisionPolicy?.id ?? "none"}</span>
            </div>
          </div>
          <div className="review-card review-selection-card">
            <span className="technical-meta-label">Multiseed preset</span>
            <div className="review-card-heading">
              <strong className="primary-label">{selectedExecutionPreset?.label ?? "Missing"}</strong>
              <span className="item-card-id">{selectedExecutionPreset?.id ?? "none"}</span>
            </div>
          </div>
        </div>

        <div className="review-card">
          <span className="technical-meta-label">Multiseed summary</span>
          <dl className="compact-grid review-summary-grid">
            <dt>Config mode</dt>
            <dd>{isExistingConfigMode ? "Reuse existing canonical config" : "Create new canonical config"}</dd>
            <dt>Seed plan</dt>
            <dd>
              {form.seed_mode === "range"
                ? `Range mode: start ${form.seed_start || "?"}, count ${form.seed_count || "?"}`
                : `Explicit seeds: ${form.explicit_seeds || "none"}`}
            </dd>
            <dt>Parallel workers inside run</dt>
            <dd>{form.parallel_workers || "?"}</dd>
            <dt>Queue concurrency limit</dt>
            <dd>{form.queue_concurrency_limit || "?"}</dd>
            <dt>Logic version</dt>
            <dd>{bootstrap.current_logic_version}</dd>
          </dl>
        </div>

        {reviewWarnings.length > 0 ? (
          <div className="warning-stack">
            {reviewWarnings.map((warning) => (
              <div key={warning} className="soft-warning">
                {warning}
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">Selection looks coherent for the canonical execution path.</p>
        )}
      </div>

      <div className="panel">
        <h2>6. Actions</h2>
        <div className="nav-actions">
          <button
            className="link-button"
            disabled={actionState !== "idle" || hasBlockingReviewIssue}
            onClick={() => void handleSave()}
            type="button"
          >
            {actionState === "saving"
              ? "Saving..."
              : isExistingConfigMode
                ? "Reuse saved config"
                : "Save run config"}
          </button>
          <button
            className="link-button secondary"
            disabled={actionState !== "idle" || hasBlockingReviewIssue}
            onClick={() => void handleSaveAndExecute()}
            type="button"
          >
            {actionState === "executing"
              ? "Submitting..."
              : isExistingConfigMode
                ? "Queue existing config"
                : "Save and queue"}
          </button>
        </div>
      </div>

      <MutationProfileModal
        contextLabel="Run Lab Authoring"
        isOpen={isMutationProfileModalOpen}
        onClose={() => setIsMutationProfileModalOpen(false)}
        onSaved={handleMutationProfileSaved}
      />
      <SignalPackModal
        contextLabel="Run Lab Authoring"
        isOpen={isSignalPackModalOpen}
        onClose={() => setIsSignalPackModalOpen(false)}
        onSaved={handleSignalPackSaved}
      />
    </div>
  );
}
