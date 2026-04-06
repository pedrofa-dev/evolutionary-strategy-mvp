import {
  Component,
  type ErrorInfo,
  type ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  compareCampaigns,
  deleteCampaign,
  getCampaignDetail,
  getCampaigns,
} from "../services/runsResultsApi";
import type {
  CampaignComparisonEntry,
  CampaignDetail,
  CampaignSummary,
} from "../types/results";

type ResultsPageProps = {
  selectedCampaignId: string | null;
  onOpenCampaign: (campaignId: string) => void;
  onOpenWorkspace: () => void;
  onOpenRunLab: () => void;
};

type ResultsRenderBoundaryProps = {
  children: ReactNode;
};

type ResultsRenderBoundaryState = {
  hasError: boolean;
};

const RESULTS_PREFERRED_CONFIG_KEY = "results-preferred-config-name";
const RESULTS_PREFERRED_LAUNCH_AT_KEY = "results-preferred-launch-at";
const RESULTS_NAVIGATION_INTENT_KEY = "results-navigation-intent";

class ResultsRenderBoundary extends Component<
  ResultsRenderBoundaryProps,
  ResultsRenderBoundaryState
> {
  constructor(props: ResultsRenderBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ResultsRenderBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Results render failed", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="panel">
          <div className="error-banner">
            <strong>Results view could not render this state.</strong>
            <div>
              The Results workspace is still available, but the selected view hit a render error.
              Try returning to the campaign list or refreshing the page state.
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

function formatMetric(value: number | null | undefined, digits = 2): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "Not available";
  }
  return value.toFixed(digits);
}

function formatPercentRatio(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "Not available";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function classificationLabel(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) {
    return "Not classified";
  }
  return sentenceCase(value.replace(/[_-]+/g, " "));
}

function sentenceCase(value: string): string {
  const normalized = value.trim();
  if (!normalized) {
    return normalized;
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function persistedText(
  value: unknown,
  fallback: string,
): string {
  if (typeof value !== "string" || !value.trim()) {
    return fallback;
  }
  return sentenceCase(value.replace(/[_-]+/g, " "));
}

function campaignStateLabel(campaign: CampaignSummary): string {
  if (campaign.status !== "completed") {
    return "Incomplete";
  }
  if (!campaign.has_champion) {
    return "No champion";
  }
  if (campaign.has_external_evaluation && !campaign.external_artifact_available) {
    return "Artifacts incomplete";
  }
  if (!campaign.has_external_evaluation) {
    return "Validation only";
  }
  return "Complete";
}

function championStatusMessage(detail: CampaignDetail): string {
  if (!detail.summary.has_champion || detail.champion === null) {
    return "No champion selected from persisted data.";
  }
  return classificationLabel(detail.champion.classification);
}

function externalStatusMessage(detail: CampaignDetail): string {
  if (!detail.evaluation.has_external_evaluation) {
    return "External reevaluation not persisted for this campaign.";
  }
  if (!detail.evaluation.external_artifact_available) {
    return "External reevaluation metadata exists, but the persisted artifact rows are missing or unreadable.";
  }
  return "External reevaluation is available from persisted reporting artifacts.";
}

function quickSummaryNote(detail: CampaignDetail): string {
  if (!detail.summary.has_quick_summary) {
    return "No persisted quick summary artifact was found for this campaign.";
  }
  return "These notes come from the persisted quick summary artifact and should be read as reporting guidance, not as recomputed truth.";
}

function incompletePersistenceNote(detail: CampaignDetail): string | null {
  if (!detail.summary.has_champion) {
    return "Campaign exists in canonical persistence, but no champion was selected for it.";
  }
  if (detail.champion?.source === "champion_row_fallback") {
    return "Campaign exists, but the persisted champion analysis card is missing. The detail view is using champion rows as a fallback.";
  }
  if (detail.evaluation.has_external_evaluation && !detail.evaluation.external_artifact_available) {
    return "Campaign exists, but external reevaluation artifact rows are missing or unreadable. Summary metrics are shown only where they were already persisted.";
  }
  if (!detail.summary.has_quick_summary) {
    return "Campaign exists, but the persisted quick summary artifact is missing.";
  }
  return null;
}

function reuseReasonSourceLabel(value: string | null | undefined): string {
  if (!value) {
    return "Reason source unavailable";
  }
  if (value === "exact_persisted_summary") {
    return "Persisted runtime summary";
  }
  if (value === "exact_prior_row") {
    return "Exact prior persisted row";
  }
  if (value === "derived_prior_match") {
    return "Derived from prior persisted matches";
  }
  if (value === "exact_no_completed_match") {
    return "Exact completed-match lookup";
  }
  return sentenceCase(value.replace(/[_-]+/g, " "));
}

function toggleSelection(items: string[], target: string): string[] {
  if (items.includes(target)) {
    return items.filter((item) => item !== target);
  }
  return [...items, target];
}

function comparisonPrompt(selectedCount: number): string {
  if (selectedCount === 0) {
    return "Select campaigns to compare robustness and stability side by side.";
  }
  if (selectedCount === 1) {
    return "Select one more campaign to open side by side comparison.";
  }
  return `${selectedCount} campaigns selected for comparison.`;
}

function parseCampaignTimestamp(value: string): number | null {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return parsed;
}

export default function ResultsPage({
  selectedCampaignId,
  onOpenCampaign,
  onOpenWorkspace,
  onOpenRunLab,
}: ResultsPageProps) {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [campaignsLoading, setCampaignsLoading] = useState(true);
  const [campaignsError, setCampaignsError] = useState<string | null>(null);
  const [detail, setDetail] = useState<CampaignDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [comparisonIds, setComparisonIds] = useState<string[]>([]);
  const [comparisonItems, setComparisonItems] = useState<CampaignComparisonEntry[]>([]);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);
  const [deleteInFlight, setDeleteInFlight] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadCampaigns() {
      try {
        setCampaignsLoading(true);
        setCampaignsError(null);
        const nextCampaigns = await getCampaigns();
        if (!cancelled) {
          setCampaigns(nextCampaigns);
        }
      } catch (loadError) {
        if (!cancelled) {
          setCampaignsError(
            loadError instanceof Error ? loadError.message : "Unknown error",
          );
        }
      } finally {
        if (!cancelled) {
          setCampaignsLoading(false);
        }
      }
    }

    void loadCampaigns();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!campaignsLoading && campaigns.length > 0 && !selectedCampaignId) {
      const navigationIntent = window.sessionStorage.getItem(
        RESULTS_NAVIGATION_INTENT_KEY,
      );

      if (navigationIntent !== "run-lab") {
        return;
      }

      const preferredConfigName = window.sessionStorage.getItem(
        RESULTS_PREFERRED_CONFIG_KEY,
      );
      const preferredLaunchAt = window.sessionStorage.getItem(
        RESULTS_PREFERRED_LAUNCH_AT_KEY,
      );
      const preferredLaunchTimestamp =
        preferredLaunchAt === null ? null : parseCampaignTimestamp(preferredLaunchAt);
      const matchingCampaigns =
        preferredConfigName === null
          ? []
          : campaigns.filter(
              (campaign) =>
                campaign.config_name === preferredConfigName ||
                campaign.config_names.includes(preferredConfigName),
            );
      const preferredCampaign =
        preferredLaunchTimestamp === null
          ? matchingCampaigns[0] ?? null
          : matchingCampaigns.find((campaign) => {
              const campaignTimestamp = parseCampaignTimestamp(campaign.created_at);
              return campaignTimestamp !== null && campaignTimestamp >= preferredLaunchTimestamp - 60_000;
            }) ?? matchingCampaigns[0] ?? null;

      window.sessionStorage.removeItem(RESULTS_NAVIGATION_INTENT_KEY);
      window.sessionStorage.removeItem(RESULTS_PREFERRED_CONFIG_KEY);
      window.sessionStorage.removeItem(RESULTS_PREFERRED_LAUNCH_AT_KEY);

      if (preferredCampaign) {
        onOpenCampaign(preferredCampaign.campaign_id);
      }
    }
  }, [campaigns, campaignsLoading, onOpenCampaign, selectedCampaignId]);

  useEffect(() => {
    if (selectedCampaignId) {
      window.sessionStorage.removeItem(RESULTS_NAVIGATION_INTENT_KEY);
      window.sessionStorage.removeItem(RESULTS_PREFERRED_CONFIG_KEY);
      window.sessionStorage.removeItem(RESULTS_PREFERRED_LAUNCH_AT_KEY);
    }
  }, [selectedCampaignId]);

  useEffect(() => {
    setDeleteConfirmOpen(false);
  }, [selectedCampaignId]);

  useEffect(() => {
    setComparisonIds((current) =>
      current.filter((campaignId) =>
        campaigns.some((campaign) => campaign.campaign_id === campaignId),
      ),
    );
  }, [campaigns]);

  useEffect(() => {
    let cancelled = false;

    async function loadDetail(campaignId: string) {
      try {
        setDetailLoading(true);
        setDetail(null);
        setDetailError(null);
        const nextDetail = await getCampaignDetail(campaignId);
        if (!cancelled) {
          setDetail(nextDetail);
        }
      } catch (loadError) {
        if (!cancelled) {
          setDetail(null);
          setDetailError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    }

    if (!selectedCampaignId) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      window.sessionStorage.removeItem(RESULTS_NAVIGATION_INTENT_KEY);
      return () => {
        cancelled = true;
      };
    }

    void loadDetail(selectedCampaignId);
    return () => {
      cancelled = true;
    };
  }, [selectedCampaignId]);

  useEffect(() => {
    let cancelled = false;

    async function loadComparison(ids: string[]) {
      try {
        setComparisonLoading(true);
        setComparisonError(null);
        const nextItems = await compareCampaigns(ids);
        if (!cancelled) {
          setComparisonItems(nextItems);
        }
      } catch (loadError) {
        if (!cancelled) {
          setComparisonItems([]);
          setComparisonError(
            loadError instanceof Error ? loadError.message : "Unknown error",
          );
        }
      } finally {
        if (!cancelled) {
          setComparisonLoading(false);
        }
      }
    }

    if (comparisonIds.length < 2) {
      setComparisonItems([]);
      setComparisonError(null);
      setComparisonLoading(false);
      return () => {
        cancelled = true;
      };
    }

    void loadComparison(comparisonIds);
    return () => {
      cancelled = true;
    };
  }, [comparisonIds]);

  const selectedSummary = useMemo(
    () =>
      selectedCampaignId
        ? campaigns.find((campaign) => campaign.campaign_id === selectedCampaignId) ?? null
        : null,
    [campaigns, selectedCampaignId],
  );

  const detailMatchesSelection =
    selectedCampaignId !== null &&
    detail !== null &&
    detail.summary.campaign_id === selectedCampaignId;
  const visibleDetail = detailMatchesSelection ? detail : null;
  const visibleDetailError = selectedCampaignId ? detailError : null;
  const visibleDetailLoading =
    selectedCampaignId !== null &&
    (detailLoading || (!detailMatchesSelection && visibleDetailError === null));

  async function handleDeleteSelectedCampaign() {
    if (!selectedCampaignId) {
      return;
    }
    try {
      setDeleteInFlight(true);
      setDeleteError(null);
      setDeleteSuccess(null);
      const result = await deleteCampaign(selectedCampaignId);
      setDeleteConfirmOpen(false);
      setComparisonIds((current) => current.filter((item) => item !== selectedCampaignId));
      setDeleteSuccess(
        `Deleted ${result.campaign_id}. Removed canonical campaign rows and ${result.deleted_artifact_paths.length} artifact paths.`,
      );
      onOpenWorkspace();
      setReloadKey((current) => current + 1);
    } catch (deleteLoadError) {
      setDeleteError(
        deleteLoadError instanceof Error ? deleteLoadError.message : "Unknown error",
      );
    } finally {
      setDeleteInFlight(false);
    }
  }

  return (
    <div className="page-grid">
      <div className="panel hero-panel">
        <p className="eyebrow">Runs / Results</p>
        <h1>Read campaigns from canonical persistence</h1>
        <p className="muted">
          This tab only reads persisted multiseed runs, champion analyses, and
          external evaluation artifacts. It does not rescore or recalculate
          strategy behavior.
        </p>
        <div className="nav-actions">
          <button className="link-button secondary" onClick={onOpenRunLab} type="button">
            Open Run Lab
          </button>
          <button
            className="link-button secondary"
            onClick={() => setReloadKey((current) => current + 1)}
            type="button"
          >
            Refresh campaigns
          </button>
        </div>
      </div>

      {campaignsError ? (
        <div className="error-banner">
          <strong>Could not load campaigns.</strong>
          <div>{campaignsError}</div>
        </div>
      ) : null}

      {deleteError ? (
        <div className="error-banner">
          <strong>Campaign delete failed.</strong>
          <div>{deleteError}</div>
        </div>
      ) : null}

      {deleteSuccess ? <div className="panel">{deleteSuccess}</div> : null}

      {campaignsLoading ? (
        <div className="panel">
          <p className="loading-text">Loading persisted campaigns...</p>
        </div>
      ) : null}

      {!campaignsLoading && campaigns.length === 0 ? (
        <div className="panel">
          <h2>No persisted runs yet</h2>
          <p className="muted">
            Run Lab can save a canonical config and launch the existing multiseed
            workflow. Results will appear here after persistence completes.
          </p>
          <div className="nav-actions">
            <button className="link-button" onClick={onOpenRunLab} type="button">
              Open Run Lab
            </button>
          </div>
        </div>
      ) : null}

      {!campaignsLoading && campaigns.length > 0 ? (
        <ResultsRenderBoundary key={selectedCampaignId ?? "results-workspace"}>
          <div className="page-grid results-layout">
          <div className="panel results-sidebar">
            <div className="results-sidebar-header">
              <h2>Campaigns</h2>
              <p className="muted">
                One campaign equals one persisted multiseed execution.
              </p>
            </div>
            <div className="results-campaign-list">
              {campaigns.map((campaign) => {
                const selected = campaign.campaign_id === selectedCampaignId;
                const compareSelected = comparisonIds.includes(campaign.campaign_id);

                return (
                  <div
                    key={campaign.campaign_id}
                    className={selected ? "campaign-card selected" : "campaign-card"}
                  >
                    <button
                      className="campaign-card-main"
                      onClick={() => onOpenCampaign(campaign.campaign_id)}
                      type="button"
                    >
                      <div className="campaign-card-header">
                        <strong className="primary-label">{campaign.config_name}</strong>
                        <span className="origin-tag origin-runtime">
                          {campaignStateLabel(campaign)}
                        </span>
                      </div>
                      <div className="item-card-id">{campaign.campaign_id}</div>
                      <div className="campaign-card-meta">
                        <span>{campaign.dataset_label}</span>
                        <span>{campaign.preset_name ?? "no preset"}</span>
                        <span>{campaign.seeds_completed} seeds</span>
                        <span>{formatDateTime(campaign.created_at)}</span>
                      </div>
                      <dl className="compact-grid">
                        <dt>Mean score</dt>
                        <dd>{formatMetric(campaign.mean_score)}</dd>
                        <dt>Std dev</dt>
                        <dd>{formatMetric(campaign.score_std_dev)}</dd>
                        <dt>Train to validation</dt>
                        <dd>
                          {formatPercentRatio(campaign.train_to_validation_survival_rate)}
                        </dd>
                        <dt>Validation to external</dt>
                        <dd>
                          {formatPercentRatio(
                            campaign.validation_to_external_survival_rate,
                          )}
                        </dd>
                        <dt>Champion</dt>
                        <dd>
                          {campaign.has_champion
                            ? classificationLabel(campaign.champion_classification)
                            : "No champion selected"}
                        </dd>
                      </dl>
                    </button>
                    <label className="compare-toggle">
                      <input
                        checked={compareSelected}
                        onChange={() =>
                          setComparisonIds((current) =>
                            toggleSelection(current, campaign.campaign_id),
                          )
                        }
                        type="checkbox"
                      />
                      Compare
                    </label>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="page-grid">
            <div className="panel">
              <div className="results-panel-header">
                <div>
                  <p className="eyebrow">Primary decision block</p>
                  <h2>Champion</h2>
                </div>
                <div className="nav-actions">
                  {selectedSummary ? (
                    <span className="muted">
                      {`${selectedSummary.config_name} | ${selectedSummary.dataset_label}`}
                    </span>
                  ) : null}
                  {selectedSummary ? (
                    <button
                      className="link-button danger-button"
                      disabled={deleteInFlight || selectedSummary.status === "running"}
                      onClick={() => {
                        setDeleteError(null);
                        setDeleteSuccess(null);
                        setDeleteConfirmOpen((current) => !current);
                      }}
                      type="button"
                    >
                      Delete campaign
                    </button>
                  ) : null}
                </div>
              </div>

              {visibleDetailLoading ? (
                <p className="loading-text">Loading campaign detail...</p>
              ) : null}

              {visibleDetailError ? (
                <div className="error-banner">
                  <strong>Campaign detail could not be loaded.</strong>
                  <div>{visibleDetailError}</div>
                  {selectedSummary ? (
                    <div>
                      The campaign exists in the database, but its persisted detail could not be read completely.
                    </div>
                  ) : null}
                  <div className="nav-actions">
                    <button
                      className="link-button secondary"
                      onClick={() => setReloadKey((current) => current + 1)}
                      type="button"
                    >
                      Refresh campaigns
                    </button>
                    <button
                      className="link-button secondary"
                      onClick={onOpenWorkspace}
                      type="button"
                    >
                      Back to results workspace
                    </button>
                    {campaigns.length > 0 ? (
                      <button
                        className="link-button secondary"
                        onClick={() => onOpenCampaign(campaigns[0].campaign_id)}
                        type="button"
                      >
                        Open latest campaign
                      </button>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {!visibleDetailLoading && !visibleDetailError && !visibleDetail ? (
                <p className="muted">Select a persisted campaign to inspect its results.</p>
              ) : null}

              {!visibleDetailLoading && visibleDetail ? (
                <div className="page-grid">
                  {deleteConfirmOpen ? (
                    <div className="soft-warning">
                      <strong>Delete this campaign?</strong>
                      <div>
                        This removes the persisted campaign row, linked run executions,
                        persisted champions, linked analysis and evaluation rows, and
                        campaign-tied artifacts when they can be identified safely.
                      </div>
                      <div>
                        Running campaigns are protected and cannot be deleted.
                      </div>
                      <div className="nav-actions">
                        <button
                          className="link-button danger-button"
                          disabled={deleteInFlight}
                          onClick={() => void handleDeleteSelectedCampaign()}
                          type="button"
                        >
                          {deleteInFlight ? "Deleting..." : "Confirm delete"}
                        </button>
                        <button
                          className="link-button secondary"
                          onClick={() => setDeleteConfirmOpen(false)}
                          type="button"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : null}

                  <div className="champion-hero">
                    <div className="champion-hero-main">
                      <p className="eyebrow">Champion status</p>
                      <h3>{championStatusMessage(visibleDetail)}</h3>
                      <p className="muted">
                        {quickSummaryNote(visibleDetail)}
                      </p>
                      {incompletePersistenceNote(visibleDetail) ? (
                        <p className="muted">
                          {incompletePersistenceNote(visibleDetail)}
                        </p>
                      ) : null}
                    </div>
                    <div className="champion-hero-metrics">
                      <div className="metric-card">
                        <span className="technical-meta-label">Score</span>
                        <strong>{formatMetric(visibleDetail.champion?.score ?? null)}</strong>
                      </div>
                      <div className="metric-card">
                        <span className="technical-meta-label">Return</span>
                        <strong>{formatMetric(visibleDetail.champion?.return_pct ?? null)}</strong>
                      </div>
                      <div className="metric-card">
                        <span className="technical-meta-label">Drawdown</span>
                        <strong>{formatMetric(visibleDetail.champion?.drawdown ?? null)}</strong>
                      </div>
                      <div className="metric-card">
                        <span className="technical-meta-label">Profit factor</span>
                        <strong>
                          {visibleDetail.champion?.profit_factor === null
                            ? "Not persisted"
                            : formatMetric(visibleDetail.champion?.profit_factor)}
                        </strong>
                      </div>
                      <div className="metric-card">
                        <span className="technical-meta-label">Trades</span>
                        <strong>{formatMetric(visibleDetail.champion?.trades ?? null, 0)}</strong>
                      </div>
                    </div>
                  </div>

                  <div className="review-grid">
                    <div className="review-card">
                      <span className="technical-meta-label">Persisted verdict note</span>
                      <strong>
                        {persistedText(
                          visibleDetail.summary.verdict,
                          "Not persisted in the quick summary artifact",
                        )}
                      </strong>
                    </div>
                    <div className="review-card">
                      <span className="technical-meta-label">Persisted likely limit</span>
                      <strong>
                        {persistedText(
                          visibleDetail.summary.likely_limit,
                          "Not persisted in the quick summary artifact",
                        )}
                      </strong>
                    </div>
                    <div className="review-card">
                      <span className="technical-meta-label">Persisted next action</span>
                      <strong>
                        {persistedText(
                          visibleDetail.summary.next_action,
                          "Not persisted in the quick summary artifact",
                        )}
                      </strong>
                    </div>
                    <div className="review-card">
                      <span className="technical-meta-label">Preset</span>
                      <strong>{visibleDetail.summary.preset_name ?? "none"}</strong>
                    </div>
                    <div className="review-card">
                      <span className="technical-meta-label">Seeds completed</span>
                      <strong>
                        {visibleDetail.summary.seeds_completed} of {visibleDetail.summary.seeds_planned}
                      </strong>
                    </div>
                  </div>

                  <div className="results-section-grid">
                    <div className="review-card">
                      <h3>Reuse / recovery</h3>
                      <dl className="compact-grid">
                        <dt>Reused seeds</dt>
                        <dd>{visibleDetail.reuse_overview.reused_count}</dd>
                        <dt>Fresh successful seeds</dt>
                        <dd>{visibleDetail.reuse_overview.fresh_success_count}</dd>
                        <dt>Failed seeds</dt>
                        <dd>{visibleDetail.reuse_overview.failed_count}</dd>
                      </dl>
                      <p className="muted">{visibleDetail.reuse_overview.message}</p>
                      <p className="muted">{visibleDetail.reuse_overview.reason_scope_note}</p>
                    </div>

                    <div className="review-card">
                      <h3>Evaluation panel</h3>
                      <dl className="compact-grid">
                        <dt>Train mean</dt>
                        <dd>{formatMetric(visibleDetail.evaluation.train_mean_score)}</dd>
                        <dt>Validation mean</dt>
                        <dd>{formatMetric(visibleDetail.evaluation.validation_mean_score)}</dd>
                        <dt>External mean</dt>
                        <dd>
                          {visibleDetail.evaluation.has_external_evaluation
                            ? formatMetric(visibleDetail.evaluation.external_mean_score)
                            : "Not reevaluated"}
                        </dd>
                        <dt>Selection gap</dt>
                        <dd>{formatMetric(visibleDetail.evaluation.selection_gap_mean)}</dd>
                        <dt>Validation std dev</dt>
                        <dd>{formatMetric(visibleDetail.evaluation.validation_score_std_dev)}</dd>
                        <dt>External valid rows</dt>
                        <dd>{visibleDetail.evaluation.external_valid_count}</dd>
                        <dt>External positive profit</dt>
                        <dd>{visibleDetail.evaluation.external_positive_profit_count}</dd>
                      </dl>
                      <p className="muted">{externalStatusMessage(visibleDetail)}</p>
                    </div>

                    <div className="review-card">
                      <h3>Campaign summary</h3>
                      <dl className="compact-grid">
                        <dt>Config</dt>
                        <dd>{visibleDetail.summary.config_name}</dd>
                        <dt>Dataset</dt>
                        <dd>{visibleDetail.summary.dataset_label}</dd>
                        <dt>Created at</dt>
                        <dd>{formatDateTime(visibleDetail.summary.created_at)}</dd>
                        <dt>Mean score</dt>
                        <dd>{formatMetric(visibleDetail.summary.mean_score)}</dd>
                        <dt>Std dev</dt>
                        <dd>{formatMetric(visibleDetail.summary.score_std_dev)}</dd>
                        <dt>Train to validation</dt>
                        <dd>
                          {formatPercentRatio(
                            visibleDetail.summary.train_to_validation_survival_rate,
                          )}
                        </dd>
                        <dt>Validation to external</dt>
                        <dd>
                          {formatPercentRatio(
                            visibleDetail.summary.validation_to_external_survival_rate,
                          )}
                        </dd>
                      </dl>
                    </div>
                  </div>

                  <details className="results-details" open>
                    <summary>Multiseed behavior</summary>
                    <div className="execution-list">
                      {visibleDetail.executions.map((execution) => (
                        <div key={execution.run_id} className="execution-card">
                          <div className="execution-card-header">
                            <strong>Seed {execution.seed}</strong>
                            <span className="origin-tag origin-runtime">
                              {classificationLabel(execution.champion_classification)}
                            </span>
                          </div>
                          <dl className="compact-grid">
                            <dt>Status</dt>
                            <dd>{execution.status}</dd>
                            <dt>Reuse</dt>
                            <dd>{execution.reuse_status ?? "Not available"}</dd>
                            <dt>Reuse reason</dt>
                            <dd>{execution.reuse_reason ?? "Not available"}</dd>
                            <dt>Reason source</dt>
                            <dd>{reuseReasonSourceLabel(execution.reuse_reason_source)}</dd>
                            <dt>Train score</dt>
                            <dd>{formatMetric(execution.train_score)}</dd>
                            <dt>Validation score</dt>
                            <dd>{formatMetric(execution.validation_score)}</dd>
                            <dt>External score</dt>
                            <dd>
                              {execution.external_status === "evaluated"
                                ? formatMetric(execution.external_score)
                                : "Not reevaluated"}
                            </dd>
                          </dl>
                        </div>
                      ))}
                    </div>
                  </details>
                </div>
              ) : null}
            </div>

            <div className="panel">
              <div className="results-panel-header">
                <div>
                  <p className="eyebrow">Decision support</p>
                  <h2>Comparison</h2>
                </div>
                <span className="muted">{comparisonPrompt(comparisonIds.length)}</span>
              </div>

              {comparisonLoading ? (
                <p className="loading-text">Loading comparison...</p>
              ) : null}

              {comparisonError ? (
                <div className="error-banner">
                  <strong>Comparison could not be loaded.</strong>
                  <div>{comparisonError}</div>
                </div>
              ) : null}

              {!comparisonLoading && comparisonIds.length < 2 ? (
                <p className="muted">
                  Pick at least two campaigns from the left column to compare
                  robustness, dispersion, and champion outcomes.
                </p>
              ) : null}

              {!comparisonLoading && comparisonItems.length >= 2 ? (
                <div className="comparison-grid">
                  {comparisonItems.map((item) => (
                    <div key={item.campaign_id} className="comparison-card">
                      <div className="comparison-card-header">
                        <strong className="primary-label">{item.config_name}</strong>
                        <span className="item-card-id">{item.campaign_id}</span>
                      </div>
                      <p className="muted">{item.dataset_label}</p>
                      <dl className="compact-grid">
                        <dt>Mean score</dt>
                        <dd>{formatMetric(item.mean_score)}</dd>
                        <dt>Std dev</dt>
                        <dd>{formatMetric(item.score_std_dev)}</dd>
                        <dt>Train to validation</dt>
                        <dd>{formatPercentRatio(item.train_to_validation_survival_rate)}</dd>
                        <dt>Validation to external</dt>
                        <dd>
                          {item.has_external_evaluation && item.external_artifact_available
                            ? formatPercentRatio(item.validation_to_external_survival_rate)
                            : item.has_external_evaluation
                              ? "Artifact missing"
                              : "Not reevaluated"}
                        </dd>
                        <dt>Champion class</dt>
                        <dd>
                          {item.has_champion
                            ? classificationLabel(item.champion_classification)
                            : "No champion selected"}
                        </dd>
                        <dt>Champion score</dt>
                        <dd>{item.has_champion ? formatMetric(item.champion_score) : "Not available"}</dd>
                        <dt>Champion return</dt>
                        <dd>
                          {item.has_champion
                            ? formatMetric(item.champion_return_pct)
                            : "Not available"}
                        </dd>
                        <dt>Champion drawdown</dt>
                        <dd>
                          {item.has_champion
                            ? formatMetric(item.champion_drawdown)
                            : "Not available"}
                        </dd>
                        <dt>Champion trades</dt>
                        <dd>
                          {item.has_champion
                            ? formatMetric(item.champion_trades, 0)
                            : "Not available"}
                        </dd>
                        <dt>Persisted summary</dt>
                        <dd>
                          {item.has_quick_summary
                            ? persistedText(item.verdict, "Summary note missing")
                            : "No quick summary artifact"}
                        </dd>
                      </dl>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
          </div>
        </ResultsRenderBoundary>
      ) : null}
    </div>
  );
}
