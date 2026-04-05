import { useEffect, useMemo, useState } from "react";

import { getDisplayLabel } from "../content/catalogMetadata";
import { getRunLabBootstrap, saveAndExecuteRun, saveRunConfig } from "../services/runLabApi";
import type {
  LaunchedRunResult,
  RunLabBootstrap,
  RunLabDatasetCatalogSummary,
  RunLabOption,
  RunLabSaveRequest,
  RunLabTemplateSummary,
  SavedRunConfigResult,
} from "../types/runLab";

type RunLabPageProps = {
  onOpenCatalog: () => void;
};

type ActionState = "idle" | "saving" | "executing";

type FormState = {
  template_config_name: string;
  config_name: string;
  dataset_catalog_id: string;
  signal_pack_name: string;
  genome_schema_name: string;
  mutation_profile_name: string;
  decision_policy_name: string;
  experiment_preset_name: string;
  seed_mode: "range" | "explicit";
  seed_start: string;
  seed_count: string;
  explicit_seeds: string;
};

function buildFormStateFromTemplate(
  template: RunLabTemplateSummary,
  bootstrap: RunLabBootstrap,
  existing?: FormState | null,
): FormState {
  return {
    template_config_name: template.id,
    config_name: existing?.config_name ?? "",
    dataset_catalog_id: template.dataset_catalog_id,
    signal_pack_name: template.signal_pack_name,
    genome_schema_name: template.genome_schema_name,
    mutation_profile_name: template.mutation_profile_name,
    decision_policy_name: template.decision_policy_name,
    experiment_preset_name:
      existing?.experiment_preset_name ?? bootstrap.defaults.experiment_preset_name,
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

  return buildFormStateFromTemplate(initialTemplate, bootstrap);
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

export default function RunLabPage({ onOpenCatalog }: RunLabPageProps) {
  const [bootstrap, setBootstrap] = useState<RunLabBootstrap | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [advancedMode, setAdvancedMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [actionState, setActionState] = useState<ActionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [savedResult, setSavedResult] = useState<SavedRunConfigResult | null>(null);
  const [launchResult, setLaunchResult] = useState<LaunchedRunResult | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadBootstrap() {
      try {
        setIsLoading(true);
        setError(null);
        const nextBootstrap = await getRunLabBootstrap();
        if (!cancelled) {
          setBootstrap(nextBootstrap);
          setForm(buildInitialFormState(nextBootstrap));
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
  }, []);

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
    return warnings;
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
      setSavedResult(result.saved_config);
      setLaunchResult(result);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unknown error");
    } finally {
      setActionState("idle");
    }
  }

  if (isLoading || !bootstrap || !form) {
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

  return (
    <div className="page-grid">
      <div className="panel hero-panel">
        <p className="eyebrow">Run Lab</p>
        <h1>Prepare and launch a canonical run</h1>
        <p className="muted">
          This flow saves a canonical config under <code>configs/runs/</code> and
          launches the existing multiseed entrypoint.
        </p>
        <div className="nav-actions">
          <button className="link-button secondary" onClick={onOpenCatalog} type="button">
            Open catalog explorer
          </button>
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
          <h2>Execution launched</h2>
          <p className="muted">
            Process <strong>{launchResult.pid}</strong> started with preset{" "}
            <strong>{launchResult.preset_name ?? "none"}</strong>.
          </p>
          <div className="technical-meta">
            <span className="technical-meta-label">Launch metadata</span>
            <code>
              config set: {launchResult.execution_configs_dir}
              {"\n"}
              log: {launchResult.launch_log_path}
            </code>
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
                  {selectedDataset.date_range_start} -> {selectedDataset.date_range_end}
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
            <span className="form-label">Signal pack</span>
            <select
              value={form.signal_pack_name}
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
            <span className="form-label">Mutation profile</span>
            <select
              value={form.mutation_profile_name}
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
          <label className="form-field">
            <span className="form-label">Run config name</span>
            <input
              type="text"
              value={form.config_name}
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
            <span className="form-label">Seed mode</span>
            <select
              value={form.seed_mode}
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
              <label className="form-field">
                <span className="form-label">Base template config</span>
                <select
                  value={form.template_config_name}
                  onChange={(event) => {
                    const nextTemplate = findTemplate(
                      bootstrap.config_templates,
                      event.target.value,
                    );
                    setForm((current) =>
                      current && nextTemplate
                        ? buildFormStateFromTemplate(nextTemplate, bootstrap, current)
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
          <div className="review-card">
            <span className="technical-meta-label">Dataset</span>
            <strong>{selectedDataset ? getDisplayLabel(selectedDataset.id) : "Missing dataset"}</strong>
            <span className="item-card-id">{selectedDataset?.id ?? "none"}</span>
          </div>
          <div className="review-card">
            <span className="technical-meta-label">Signal pack</span>
            <strong>{selectedSignalPack?.label ?? "Missing"}</strong>
            <span className="item-card-id">{selectedSignalPack?.id ?? "none"}</span>
          </div>
          <div className="review-card">
            <span className="technical-meta-label">Genome schema</span>
            <strong>{selectedGenomeSchema?.label ?? "Missing"}</strong>
            <span className="item-card-id">{selectedGenomeSchema?.id ?? "none"}</span>
          </div>
          <div className="review-card">
            <span className="technical-meta-label">Mutation profile</span>
            <strong>{selectedMutationProfile?.label ?? "Missing"}</strong>
            <span className="item-card-id">{selectedMutationProfile?.id ?? "none"}</span>
          </div>
          <div className="review-card">
            <span className="technical-meta-label">Decision policy</span>
            <strong>{selectedDecisionPolicy?.label ?? "Missing"}</strong>
            <span className="item-card-id">{selectedDecisionPolicy?.id ?? "none"}</span>
          </div>
          <div className="review-card">
            <span className="technical-meta-label">Multiseed preset</span>
            <strong>{selectedExecutionPreset?.label ?? "Missing"}</strong>
            <span className="item-card-id">{selectedExecutionPreset?.id ?? "none"}</span>
          </div>
        </div>

        <div className="review-card">
          <span className="technical-meta-label">Multiseed summary</span>
          <p className="muted">
            {form.seed_mode === "range"
              ? `Range mode: start ${form.seed_start || "?"}, count ${form.seed_count || "?"}`
              : `Explicit seeds: ${form.explicit_seeds || "none"}`}
          </p>
          <p className="muted">
            Logic version: <strong>{bootstrap.current_logic_version}</strong>
          </p>
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
            disabled={actionState !== "idle" || reviewWarnings.some((warning) => warning.includes("required"))}
            onClick={() => void handleSave()}
            type="button"
          >
            {actionState === "saving" ? "Saving..." : "Save run config"}
          </button>
          <button
            className="link-button secondary"
            disabled={actionState !== "idle" || reviewWarnings.some((warning) => warning.includes("required"))}
            onClick={() => void handleSaveAndExecute()}
            type="button"
          >
            {actionState === "executing" ? "Launching..." : "Save and execute"}
          </button>
        </div>
      </div>
    </div>
  );
}
