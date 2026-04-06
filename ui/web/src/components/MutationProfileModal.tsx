import { useEffect, useState } from "react";

import { saveMutationProfileAsset } from "../services/runLabApi";
import type {
  MutationProfileAuthoringRequest,
  SavedMutationProfileAssetResult,
} from "../types/runLab";

type MutationProfileModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSaved: (result: SavedMutationProfileAssetResult) => Promise<void> | void;
  contextLabel?: string;
};

type FormState = {
  id: string;
  description: string;
  strong_mutation_probability: string;
  numeric_delta_scale: string;
  flag_flip_probability: string;
  weight_delta: string;
  window_step_mode: string;
};

const INITIAL_FORM: FormState = {
  id: "",
  description: "",
  strong_mutation_probability: "0.10",
  numeric_delta_scale: "1.0",
  flag_flip_probability: "0.05",
  weight_delta: "0.20",
  window_step_mode: "default",
};

function buildRequest(form: FormState): MutationProfileAuthoringRequest {
  return {
    id: form.id.trim(),
    description: form.description.trim(),
    strong_mutation_probability: Number(form.strong_mutation_probability),
    numeric_delta_scale: Number(form.numeric_delta_scale),
    flag_flip_probability: Number(form.flag_flip_probability),
    weight_delta: Number(form.weight_delta),
    window_step_mode: form.window_step_mode.trim(),
  };
}

export default function MutationProfileModal({
  isOpen,
  onClose,
  onSaved,
  contextLabel = "Run Lab Authoring",
}: MutationProfileModalProps) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setForm(INITIAL_FORM);
      setError(null);
      setIsSaving(false);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  async function handleSave() {
    try {
      setIsSaving(true);
      setError(null);
      const result = await saveMutationProfileAsset(buildRequest(form));
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
        aria-labelledby="new-mutation-profile-title"
        aria-modal="true"
        className="modal-panel"
        role="dialog"
      >
        <div className="results-panel-header">
          <div>
            <p className="eyebrow">{contextLabel}</p>
            <h2 id="new-mutation-profile-title">New Mutation Profile</h2>
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
              placeholder="example: run_lab_profile_v1"
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
              placeholder="Short note about what this profile is for."
            />
          </label>

          <div className="inline-fields">
            <label className="form-field">
              <span className="form-label">Strong mutation probability</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={form.strong_mutation_probability}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    strong_mutation_probability: event.target.value,
                  }))
                }
              />
            </label>

            <label className="form-field">
              <span className="form-label">Numeric delta scale</span>
              <input
                type="number"
                min="0"
                step="0.1"
                value={form.numeric_delta_scale}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    numeric_delta_scale: event.target.value,
                  }))
                }
              />
            </label>
          </div>

          <div className="inline-fields">
            <label className="form-field">
              <span className="form-label">Flag flip probability</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={form.flag_flip_probability}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    flag_flip_probability: event.target.value,
                  }))
                }
              />
            </label>

            <label className="form-field">
              <span className="form-label">Weight delta</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.weight_delta}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    weight_delta: event.target.value,
                  }))
                }
              />
            </label>
          </div>

          <label className="form-field">
            <span className="form-label">Window step mode</span>
            <select
              value={form.window_step_mode}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  window_step_mode: event.target.value,
                }))
              }
            >
              <option value="small">Small</option>
              <option value="default">Default</option>
              <option value="wide">Wide</option>
            </select>
          </label>
        </div>

        <div className="nav-actions">
          <button className="link-button" onClick={() => void handleSave()} type="button">
            {isSaving ? "Saving..." : "Save mutation profile"}
          </button>
          <button className="link-button secondary" onClick={onClose} type="button">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
