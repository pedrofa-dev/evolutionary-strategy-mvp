import { useEffect, useMemo, useState } from "react";

import { saveSignalPackAsset } from "../services/runLabApi";
import type {
  SavedSignalPackAssetResult,
  SignalAuthoringOption,
  SignalPackAuthoringRequest,
} from "../types/runLab";

type SignalPackModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSaved: (result: SavedSignalPackAssetResult) => Promise<void> | void;
  signalOptions: SignalAuthoringOption[];
  contextLabel?: string;
};

type FormState = {
  id: string;
  description: string;
  searchQuery: string;
  selectedSignalIds: string[];
};

const INITIAL_FORM: FormState = {
  id: "",
  description: "",
  searchQuery: "",
  selectedSignalIds: [],
};

export function serializeSignalPackRequest(
  form: FormState,
): SignalPackAuthoringRequest {
  return {
    id: form.id.trim(),
    description: form.description.trim(),
    signals: form.selectedSignalIds.join("\n"),
  };
}

function getSignalLabel(option: SignalAuthoringOption): string {
  return option.label ?? option.id;
}

export default function SignalPackModal({
  isOpen,
  onClose,
  onSaved,
  signalOptions,
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

  const filteredSignalOptions = useMemo(() => {
    const query = form.searchQuery.trim().toLowerCase();
    return signalOptions.filter((option) => {
      if (form.selectedSignalIds.includes(option.id)) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        option.id.toLowerCase().includes(query) ||
        (option.label ?? "").toLowerCase().includes(query) ||
        (option.description ?? "").toLowerCase().includes(query)
      );
    });
  }, [form.searchQuery, form.selectedSignalIds, signalOptions]);

  if (!isOpen) {
    return null;
  }

  function handleAddSignal(signalId: string) {
    setForm((current) => {
      if (current.selectedSignalIds.includes(signalId)) {
        return current;
      }
      return {
        ...current,
        selectedSignalIds: [...current.selectedSignalIds, signalId],
      };
    });
  }

  function handleRemoveSignal(signalId: string) {
    setForm((current) => ({
      ...current,
      selectedSignalIds: current.selectedSignalIds.filter(
        (selectedId) => selectedId !== signalId,
      ),
    }));
  }

  function handleMoveSignal(signalId: string, direction: "up" | "down") {
    setForm((current) => {
      const index = current.selectedSignalIds.indexOf(signalId);
      if (index < 0) {
        return current;
      }

      const nextIndex = direction === "up" ? index - 1 : index + 1;
      if (nextIndex < 0 || nextIndex >= current.selectedSignalIds.length) {
        return current;
      }

      const nextSelected = [...current.selectedSignalIds];
      const [movedSignal] = nextSelected.splice(index, 1);
      nextSelected.splice(nextIndex, 0, movedSignal);

      return {
        ...current,
        selectedSignalIds: nextSelected,
      };
    });
  }

  async function handleSave() {
    if (form.selectedSignalIds.length === 0) {
      setError("Select at least one signal before saving.");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      const result = await saveSignalPackAsset(serializeSignalPackRequest(form));
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

          <div className="signal-builder-grid">
            <div className="signal-builder-panel">
              <label className="form-field">
                <span className="form-label">Find signals</span>
                <input
                  type="text"
                  value={form.searchQuery}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      searchQuery: event.target.value,
                    }))
                  }
                  placeholder="Search current signal ids"
                />
              </label>

              <div className="signal-builder-summary muted">
                {signalOptions.length === 0
                  ? "No signal identifiers are currently available for authoring."
                  : `${filteredSignalOptions.length} available`}
              </div>

              {signalOptions.length === 0 ? (
                <p className="signal-builder-empty muted">
                  No current signal identifiers were exposed by the backend bootstrap.
                </p>
              ) : filteredSignalOptions.length === 0 ? (
                <p className="signal-builder-empty muted">No matching signals.</p>
              ) : (
                <div className="signal-option-list">
                  {filteredSignalOptions.map((option) => (
                    <div key={option.id} className="signal-option-row">
                      <div className="signal-option-main">
                        <strong>{getSignalLabel(option)}</strong>
                        <span className="item-card-id">{option.id}</span>
                        {option.description ? (
                          <span className="muted">{option.description}</span>
                        ) : null}
                      </div>
                      <button
                        className="link-button secondary inline-action-button"
                        onClick={() => handleAddSignal(option.id)}
                        type="button"
                      >
                        Add
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="signal-builder-panel">
              <div className="signal-builder-panel-header">
                <div>
                  <span className="form-label">Selected signals</span>
                  <p className="signal-builder-summary muted">
                    {form.selectedSignalIds.length} selected
                  </p>
                </div>
              </div>

              {form.selectedSignalIds.length === 0 ? (
                <p className="signal-builder-empty muted">No signals selected yet.</p>
              ) : (
                <div className="selected-signal-list">
                  {form.selectedSignalIds.map((signalId, index) => (
                    <div key={signalId} className="selected-signal-row">
                      <span className="selected-signal-index">{index + 1}</span>
                      <span className="selected-signal-label">{signalId}</span>
                      <div className="selected-signal-actions">
                        <button
                          className="link-button secondary inline-action-button subtle-inline-action-button"
                          disabled={index === 0}
                          onClick={() => handleMoveSignal(signalId, "up")}
                          type="button"
                        >
                          Up
                        </button>
                        <button
                          className="link-button secondary inline-action-button subtle-inline-action-button"
                          disabled={index === form.selectedSignalIds.length - 1}
                          onClick={() => handleMoveSignal(signalId, "down")}
                          type="button"
                        >
                          Down
                        </button>
                        <button
                          className="link-button secondary inline-action-button subtle-inline-action-button"
                          onClick={() => handleRemoveSignal(signalId)}
                          type="button"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <p className="muted">
            This builder stays intentionally narrow: it only composes the current ordered signal
            ids and saves through the existing canonical signal-pack authoring path.
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
