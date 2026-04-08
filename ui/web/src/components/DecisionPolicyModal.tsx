import { useEffect, useMemo, useState } from "react";

import { saveDecisionPolicyAsset } from "../services/runLabApi";
import type {
  DecisionPolicyAuthoringMetadata,
  DecisionPolicyAuthoringRequest,
  SavedDecisionPolicyAssetResult,
} from "../types/runLab";

type DecisionPolicyModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSaved: (result: SavedDecisionPolicyAssetResult) => Promise<void> | void;
  authoring: DecisionPolicyAuthoringMetadata;
  contextLabel?: string;
};

type MappingRow = {
  signal: string;
  weight_gene_field: string;
};

type FormState = {
  id: string;
  description: string;
  engine: string;
  mappings: MappingRow[];
};

function buildInitialForm(authoring: DecisionPolicyAuthoringMetadata): FormState {
  return {
    id: "",
    description: "",
    engine: authoring.engine_options[0]?.id ?? "",
    mappings: authoring.entry_signal_options.map((option, index) => ({
      signal: option.id,
      weight_gene_field: authoring.weight_gene_field_options[index]?.id ?? "",
    })),
  };
}

export function serializeDecisionPolicyRequest(
  form: FormState,
  authoring: DecisionPolicyAuthoringMetadata,
): DecisionPolicyAuthoringRequest {
  return {
    id: form.id.trim(),
    description: form.description.trim(),
    engine: form.engine.trim(),
    entry: {
      trigger_gene: authoring.fixed_gene_bindings.entry_trigger_gene,
      signals: form.mappings.map((mapping) => ({
        signal: mapping.signal,
        weight_gene_field: mapping.weight_gene_field.trim(),
      })),
    },
    exit: {
      policy_gene: authoring.fixed_gene_bindings.exit_policy_gene,
      trade_control_gene: authoring.fixed_gene_bindings.trade_control_gene,
    },
  };
}

function getOptionLabel(option: { id: string; label?: string; description?: string }): string {
  return option.label ?? option.id;
}

export default function DecisionPolicyModal({
  isOpen,
  onClose,
  onSaved,
  authoring,
  contextLabel = "Run Lab Authoring",
}: DecisionPolicyModalProps) {
  const [form, setForm] = useState<FormState>(() => buildInitialForm(authoring));
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setForm(buildInitialForm(authoring));
      setError(null);
      setIsSaving(false);
    }
  }, [authoring, isOpen]);

  const duplicateWeightFields = useMemo(() => {
    const counts = new Map<string, number>();
    for (const mapping of form.mappings) {
      const normalized = mapping.weight_gene_field.trim();
      if (!normalized) {
        continue;
      }
      counts.set(normalized, (counts.get(normalized) ?? 0) + 1);
    }
    return new Set(
      [...counts.entries()]
        .filter(([, count]) => count > 1)
        .map(([fieldName]) => fieldName),
    );
  }, [form.mappings]);

  if (!isOpen) {
    return null;
  }

  function updateMapping(signalId: string, weightGeneField: string) {
    setForm((current) => ({
      ...current,
      mappings: current.mappings.map((mapping) =>
        mapping.signal === signalId ? { ...mapping, weight_gene_field: weightGeneField } : mapping,
      ),
    }));
  }

  async function handleSave() {
    if (!form.id.trim()) {
      setError("Decision policy id is required.");
      return;
    }
    if (!form.engine.trim()) {
      setError("Decision policy engine is required.");
      return;
    }
    if (form.mappings.length !== authoring.entry_signal_options.length) {
      setError("The weighted policy lane requires every supported signal row.");
      return;
    }
    if (form.mappings.some((mapping) => !mapping.weight_gene_field.trim())) {
      setError("Every signal family row needs a weight gene field.");
      return;
    }
    if (duplicateWeightFields.size > 0) {
      setError("Each weight gene field can only be assigned once.");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      const result = await saveDecisionPolicyAsset(
        serializeDecisionPolicyRequest(form, authoring),
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
        aria-labelledby="new-decision-policy-title"
        aria-modal="true"
        className="modal-panel"
        role="dialog"
      >
        <div className="results-panel-header">
          <div>
            <p className="eyebrow">{contextLabel}</p>
            <h2 id="new-decision-policy-title">New Decision Policy</h2>
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
              placeholder="example: weighted_policy_variant_v1"
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
              placeholder="Short note about what this weighted policy wiring is for."
            />
          </label>

          <label className="form-field">
            <span className="form-label">Engine</span>
            <select
              value={form.engine}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  engine: event.target.value,
                }))
              }
            >
              {authoring.engine_options.map((option) => (
                <option key={option.id} value={option.id}>
                  {getOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>

          <div className="signal-builder-panel">
            <div className="signal-builder-panel-header">
              <div>
                <span className="form-label">Fixed gene bindings</span>
                <p className="signal-builder-summary muted">
                  This weighted-policy lane keeps gene ownership fixed.
                </p>
              </div>
            </div>
            <dl className="compact-grid review-summary-grid decision-policy-fixed-bindings">
              <dt>Entry trigger gene</dt>
              <dd>{authoring.fixed_gene_bindings.entry_trigger_gene}</dd>
              <dt>Exit policy gene</dt>
              <dd>{authoring.fixed_gene_bindings.exit_policy_gene}</dd>
              <dt>Trade control gene</dt>
              <dd>{authoring.fixed_gene_bindings.trade_control_gene}</dd>
            </dl>
          </div>

          <div className="signal-builder-panel">
            <div className="signal-builder-panel-header">
              <div>
                <span className="form-label">Weighted entry mapping</span>
                <p className="signal-builder-summary muted">
                  Complete the current supported signal-family to weight-field wiring.
                </p>
              </div>
            </div>

            <div className="decision-policy-mapping-list">
              {form.mappings.map((mapping, index) => {
                const duplicateField =
                  mapping.weight_gene_field.trim().length > 0 &&
                  duplicateWeightFields.has(mapping.weight_gene_field.trim());
                return (
                  <div key={mapping.signal} className="decision-policy-mapping-row">
                    <span className="selected-signal-index">{index + 1}</span>
                    <div className="decision-policy-mapping-signal">
                      <span className="form-label">Signal family</span>
                      <strong>{mapping.signal}</strong>
                    </div>
                    <label className="form-field decision-policy-mapping-field">
                      <span className="form-label">Weight gene field</span>
                      <select
                        value={mapping.weight_gene_field}
                        onChange={(event) => updateMapping(mapping.signal, event.target.value)}
                      >
                        <option value="">Select weight field</option>
                        {authoring.weight_gene_field_options.map((option) => (
                          <option key={option.id} value={option.id}>
                            {getOptionLabel(option)}
                          </option>
                        ))}
                      </select>
                      {duplicateField ? (
                        <span className="field-error-text">
                          This weight gene field is already assigned.
                        </span>
                      ) : null}
                    </label>
                  </div>
                );
              })}
            </div>
          </div>

          <p className="muted">
            This builder is intentionally narrow: it only authors the current weighted policy lane
            and saves through the canonical decision-policy authoring path.
          </p>
        </div>

        <div className="nav-actions">
          <button className="link-button" onClick={() => void handleSave()} type="button">
            {isSaving ? "Saving..." : "Save decision policy"}
          </button>
          <button className="link-button secondary" onClick={onClose} type="button">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
