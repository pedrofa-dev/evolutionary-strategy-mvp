import { useEffect, useState } from "react";

import { saveSignalPackAsset } from "../services/runLabApi";
import type { SavedSignalPackAssetResult, SignalPackAuthoringRequest } from "../types/runLab";

type SignalPackModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSaved: (result: SavedSignalPackAssetResult) => Promise<void> | void;
  contextLabel?: string;
};

type FormState = {
  id: string;
  description: string;
  signals: string;
};

const INITIAL_FORM: FormState = {
  id: "",
  description: "",
  signals: "trend_strength_medium\ntrend_strength_long\nmomentum_short",
};

function buildRequest(form: FormState): SignalPackAuthoringRequest {
  return {
    id: form.id.trim(),
    description: form.description.trim(),
    signals: form.signals,
  };
}

export default function SignalPackModal({
  isOpen,
  onClose,
  onSaved,
  contextLabel = "Run Lab Authoring",
}: SignalPackModalProps) {
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
      const result = await saveSignalPackAsset(buildRequest(form));
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
        aria-labelledby="new-signal-pack-title"
        aria-modal="true"
        className="modal-panel"
        role="dialog"
      >
        <div className="results-panel-header">
          <div>
            <p className="eyebrow">{contextLabel}</p>
            <h2 id="new-signal-pack-title">New Signal Pack</h2>
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
              placeholder="example: run_lab_signal_pack_v1"
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
              placeholder="Short note about what this signal pack is for."
            />
          </label>

          <label className="form-field">
            <span className="form-label">Signals</span>
            <textarea
              rows={8}
              value={form.signals}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  signals: event.target.value,
                }))
              }
              placeholder={"One signal identifier per line"}
            />
          </label>
          <p className="muted">
            Use the current signal vocabulary identifiers, one per line. This first version keeps
            signal pack authoring intentionally simple.
          </p>
        </div>

        <div className="nav-actions">
          <button className="link-button" onClick={() => void handleSave()} type="button">
            {isSaving ? "Saving..." : "Save signal pack"}
          </button>
          <button className="link-button secondary" onClick={onClose} type="button">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
