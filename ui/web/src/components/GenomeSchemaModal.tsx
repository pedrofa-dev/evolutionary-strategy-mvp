import { useEffect, useMemo, useState } from "react";

import { saveGenomeSchemaAsset } from "../services/runLabApi";
import type {
  GenomeSchemaAuthoringModule,
  GenomeSchemaAuthoringOption,
  GenomeSchemaAuthoringRequest,
  GenomeSchemaSuggestedModule,
  SavedGenomeSchemaAssetResult,
} from "../types/runLab";

type GenomeSchemaModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSaved: (result: SavedGenomeSchemaAssetResult) => Promise<void> | void;
  geneCatalogOptions: GenomeSchemaAuthoringOption[];
  geneTypeOptions: GenomeSchemaAuthoringOption[];
  suggestedModules: GenomeSchemaSuggestedModule[];
  contextLabel?: string;
};

type FormState = {
  id: string;
  description: string;
  geneCatalog: string;
  modules: GenomeSchemaAuthoringModule[];
};

function buildInitialForm(
  geneCatalogOptions: GenomeSchemaAuthoringOption[],
  suggestedModules: GenomeSchemaSuggestedModule[],
): FormState {
  return {
    id: "",
    description: "",
    geneCatalog: geneCatalogOptions[0]?.id ?? "",
    modules: suggestedModules.map((module) => ({
      name: module.name,
      gene_type: module.gene_type,
      required: module.required,
    })),
  };
}

export function serializeGenomeSchemaRequest(
  form: FormState,
): GenomeSchemaAuthoringRequest {
  return {
    id: form.id.trim(),
    description: form.description.trim(),
    gene_catalog: form.geneCatalog.trim(),
    modules: form.modules.map((module) => ({
      name: module.name.trim(),
      gene_type: module.gene_type.trim(),
      required: module.required,
    })),
  };
}

function getOptionLabel(option: GenomeSchemaAuthoringOption): string {
  return option.label ?? option.id;
}

export default function GenomeSchemaModal({
  isOpen,
  onClose,
  onSaved,
  geneCatalogOptions,
  geneTypeOptions,
  suggestedModules,
  contextLabel = "Run Lab Authoring",
}: GenomeSchemaModalProps) {
  const [form, setForm] = useState<FormState>(() =>
    buildInitialForm(geneCatalogOptions, suggestedModules),
  );
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setForm(buildInitialForm(geneCatalogOptions, suggestedModules));
      setError(null);
      setIsSaving(false);
    }
  }, [geneCatalogOptions, isOpen, suggestedModules]);

  const duplicateModuleNames = useMemo(() => {
    const counts = new Map<string, number>();
    for (const module of form.modules) {
      const normalized = module.name.trim();
      if (!normalized) {
        continue;
      }
      counts.set(normalized, (counts.get(normalized) ?? 0) + 1);
    }
    return new Set(
      [...counts.entries()]
        .filter(([, count]) => count > 1)
        .map(([moduleName]) => moduleName),
    );
  }, [form.modules]);

  if (!isOpen) {
    return null;
  }

  function updateModule(
    index: number,
    patch: Partial<GenomeSchemaAuthoringModule>,
  ) {
    setForm((current) => ({
      ...current,
      modules: current.modules.map((module, moduleIndex) =>
        moduleIndex === index ? { ...module, ...patch } : module,
      ),
    }));
  }

  function handleAddModule() {
    const defaultGeneType = geneTypeOptions[0]?.id ?? "";
    setForm((current) => ({
      ...current,
      modules: [
        ...current.modules,
        {
          name: "",
          gene_type: defaultGeneType,
          required: true,
        },
      ],
    }));
  }

  function handleRemoveModule(index: number) {
    setForm((current) => ({
      ...current,
      modules: current.modules.filter((_, moduleIndex) => moduleIndex !== index),
    }));
  }

  function handleMoveModule(index: number, direction: "up" | "down") {
    setForm((current) => {
      const nextIndex = direction === "up" ? index - 1 : index + 1;
      if (nextIndex < 0 || nextIndex >= current.modules.length) {
        return current;
      }
      const nextModules = [...current.modules];
      const [movedModule] = nextModules.splice(index, 1);
      nextModules.splice(nextIndex, 0, movedModule);
      return {
        ...current,
        modules: nextModules,
      };
    });
  }

  function handleResetSuggestedModules() {
    setForm((current) => ({
      ...current,
      modules: suggestedModules.map((module) => ({
        name: module.name,
        gene_type: module.gene_type,
        required: module.required,
      })),
    }));
  }

  async function handleSave() {
    if (!form.id.trim()) {
      setError("Genome schema id is required.");
      return;
    }
    if (!form.geneCatalog.trim()) {
      setError("Select a gene catalog before saving.");
      return;
    }
    if (form.modules.length === 0) {
      setError("Add at least one module before saving.");
      return;
    }
    if (form.modules.some((module) => !module.name.trim() || !module.gene_type.trim())) {
      setError("Every module needs both a name and a gene type.");
      return;
    }
    if (duplicateModuleNames.size > 0) {
      setError("Duplicate module names are not allowed.");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      const result = await saveGenomeSchemaAsset(
        serializeGenomeSchemaRequest(form),
      );
      await onSaved(result);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unknown error");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div
        aria-labelledby="new-genome-schema-title"
        aria-modal="true"
        className="modal-panel"
        role="dialog"
      >
        <div className="results-panel-header">
          <div>
            <p className="eyebrow">{contextLabel}</p>
            <h2 id="new-genome-schema-title">New Genome Schema</h2>
          </div>
          <button className="link-button secondary" onClick={onClose} type="button">
            Cancel
          </button>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="modal-form-grid">
          <label className="form-field">
            <span className="form-label">Id</span>
            <input
              type="text"
              value={form.id}
              onChange={(event) =>
                setForm((current) => ({ ...current, id: event.target.value }))
              }
              placeholder="example: run_lab_genome_schema_v1"
            />
          </label>

          <label className="form-field">
            <span className="form-label">Description</span>
            <textarea
              rows={3}
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  description: event.target.value,
                }))
              }
              placeholder="Short note about this structural genome schema."
            />
          </label>

          <label className="form-field">
            <span className="form-label">Gene catalog</span>
            <select
              value={form.geneCatalog}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  geneCatalog: event.target.value,
                }))
              }
            >
              {geneCatalogOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {getOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>

          <div className="signal-builder-panel">
            <div className="signal-builder-panel-header">
              <div>
                <span className="form-label">Modules</span>
                <p className="signal-builder-summary muted">
                  {form.modules.length} configured
                </p>
              </div>
              <div className="module-builder-toolbar">
                <button
                  className="link-button secondary inline-action-button"
                  onClick={handleResetSuggestedModules}
                  type="button"
                >
                  Use suggested layout
                </button>
                <button
                  className="link-button secondary inline-action-button"
                  onClick={handleAddModule}
                  type="button"
                >
                  Add module
                </button>
              </div>
            </div>

            {form.modules.length === 0 ? (
              <p className="signal-builder-empty muted">No modules configured yet.</p>
            ) : (
              <div className="module-row-list">
                {form.modules.map((module, index) => {
                  const trimmedName = module.name.trim();
                  const hasDuplicateName =
                    trimmedName.length > 0 && duplicateModuleNames.has(trimmedName);
                  return (
                    <div key={`${index}-${module.name}-${module.gene_type}`} className="module-row">
                      <span className="selected-signal-index">{index + 1}</span>
                      <div className="module-row-fields">
                        <label className="form-field module-row-field">
                          <span className="form-label">Name</span>
                          <input
                            type="text"
                            value={module.name}
                            onChange={(event) =>
                              updateModule(index, { name: event.target.value })
                            }
                            placeholder="example: entry_context"
                          />
                        </label>

                        <label className="form-field module-row-field">
                          <span className="form-label">Gene type</span>
                          <select
                            value={module.gene_type}
                            onChange={(event) =>
                              updateModule(index, { gene_type: event.target.value })
                            }
                          >
                            {geneTypeOptions.map((option) => (
                              <option key={option.id} value={option.id}>
                                {getOptionLabel(option)}
                              </option>
                            ))}
                          </select>
                        </label>

                        <label className="form-field module-row-toggle">
                          <span className="form-label">Required</span>
                          <div className="module-required-toggle">
                            <input
                              checked={module.required}
                              onChange={(event) =>
                                updateModule(index, { required: event.target.checked })
                              }
                              type="checkbox"
                            />
                            <span>{module.required ? "Required" : "Optional"}</span>
                          </div>
                        </label>

                        {hasDuplicateName ? (
                          <p className="soft-warning">
                            Duplicate module name. Choose a unique name before saving.
                          </p>
                        ) : null}
                      </div>

                      <div className="selected-signal-actions module-row-actions">
                        <button
                          className="link-button secondary inline-action-button subtle-inline-action-button"
                          disabled={index === 0}
                          onClick={() => handleMoveModule(index, "up")}
                          type="button"
                        >
                          Up
                        </button>
                        <button
                          className="link-button secondary inline-action-button subtle-inline-action-button"
                          disabled={index === form.modules.length - 1}
                          onClick={() => handleMoveModule(index, "down")}
                          type="button"
                        >
                          Down
                        </button>
                        <button
                          className="link-button secondary inline-action-button subtle-inline-action-button"
                          onClick={() => handleRemoveModule(index)}
                          type="button"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <p className="muted">
            This builder stays structural on purpose: it only authors the current
            gene catalog, ordered modules, and required flags already supported by
            the canonical declarative genome schema path.
          </p>
        </div>

        <div className="nav-actions">
          <button className="link-button" onClick={() => void handleSave()} type="button">
            {isSaving ? "Saving..." : "Save genome schema"}
          </button>
          <button className="link-button secondary" onClick={onClose} type="button">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
