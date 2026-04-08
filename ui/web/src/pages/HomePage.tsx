import { useEffect, useMemo, useState } from "react";

import { getExecutionMonitorItems, getCampaigns } from "../services/runsResultsApi";
import type { CampaignSummary, ExecutionMonitorItem } from "../types/results";

type HomePageProps = {
  onOpenRunLab: () => void;
  onOpenConfigs: () => void;
  onOpenResults: (campaignId?: string | null) => void;
  onOpenCatalog: () => void;
  onOpenDecisionPolicyAuthoring: () => void;
  onOpenGenomeSchemaAuthoring: () => void;
  onOpenMutationProfileAuthoring: () => void;
  onOpenSignalPackAuthoring: () => void;
};

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

function sentenceCase(value: string): string {
  const normalized = value.trim();
  if (!normalized) {
    return normalized;
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1).replace(/[_-]+/g, " ");
}

function statusLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "completed") {
    return "Finished";
  }
  if (normalized === "queued") {
    return "Queued";
  }
  if (normalized === "launching") {
    return "Launching";
  }
  if (normalized === "cancelled") {
    return "Cancelled";
  }
  return sentenceCase(value);
}

export default function HomePage({
  onOpenRunLab,
  onOpenConfigs,
  onOpenResults,
  onOpenCatalog,
  onOpenDecisionPolicyAuthoring,
  onOpenGenomeSchemaAuthoring,
  onOpenMutationProfileAuthoring,
  onOpenSignalPackAuthoring,
}: HomePageProps) {
  const [monitorItems, setMonitorItems] = useState<ExecutionMonitorItem[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadHomeData() {
      try {
        setIsLoading(true);
        setError(null);
        const [monitorResult, campaignsResult] = await Promise.allSettled([
          getExecutionMonitorItems(),
          getCampaigns(),
        ]);
        if (!cancelled) {
          setMonitorItems(
            monitorResult.status === "fulfilled" ? monitorResult.value : [],
          );
          setCampaigns(
            campaignsResult.status === "fulfilled" ? campaignsResult.value : [],
          );
          if (monitorResult.status === "rejected" || campaignsResult.status === "rejected") {
            const messages = [
              monitorResult.status === "rejected"
                ? monitorResult.reason instanceof Error
                  ? monitorResult.reason.message
                  : "Execution summary unavailable"
                : null,
              campaignsResult.status === "rejected"
                ? campaignsResult.reason instanceof Error
                  ? campaignsResult.reason.message
                  : "Recent campaigns unavailable"
                : null,
            ].filter(Boolean);
            setError(messages.join(" | "));
          }
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

    void loadHomeData();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeItems = useMemo(
    () => monitorItems.filter((item) => ["running", "launching"].includes(item.status)),
    [monitorItems],
  );
  const queuedItems = useMemo(
    () => monitorItems.filter((item) => item.status === "queued"),
    [monitorItems],
  );
  const recentItems = useMemo(
    () =>
      monitorItems.filter(
        (item) => !["running", "launching", "queued"].includes(item.status) && item.is_recent,
      ),
    [monitorItems],
  );
  const highlightedMonitorItems = useMemo(
    () => (activeItems.length > 0 ? activeItems : queuedItems.length > 0 ? queuedItems : recentItems).slice(0, 2),
    [activeItems, queuedItems, recentItems],
  );
  const recentCampaigns = useMemo(() => campaigns.slice(0, 4), [campaigns]);

  return (
    <div className="page-grid">
      <div className="panel hero-panel">
        <p className="eyebrow">Lab Home</p>
        <h1>Research workbench</h1>
        <p className="muted">
          Start from what is running now, jump into a new run, or move into
          results and reusable components without treating Catalog as the main
          entrypoint.
        </p>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="home-grid">
        <div className="panel">
          <div className="results-panel-header">
            <div>
              <p className="eyebrow">Operational pulse</p>
              <h2>Active / Recent executions</h2>
            </div>
            <button className="link-button secondary" onClick={() => onOpenResults()} type="button">
              Open Results
            </button>
          </div>
          {isLoading ? (
            <p className="loading-text">Loading execution summary...</p>
          ) : (
            <>
              <div className="review-grid home-metric-grid">
                <div className="review-card">
                  <span className="technical-meta-label">Active now</span>
                  <strong className="home-metric-value">{activeItems.length}</strong>
                </div>
                <div className="review-card">
                  <span className="technical-meta-label">Queued now</span>
                  <strong className="home-metric-value">{queuedItems.length}</strong>
                </div>
              </div>
              {highlightedMonitorItems.length > 0 ? (
                <div className="home-compact-list">
                  {highlightedMonitorItems.map((item) => (
                    <div key={item.campaign_id} className="home-list-row">
                      <div className="home-list-row-main">
                        <strong className="primary-label">{item.config_name}</strong>
                        <div className="campaign-card-meta">
                          <span>{statusLabel(item.status)}</span>
                          <span>{`${item.seeds_finished} / ${item.seeds_total} seeds`}</span>
                          <span>{`${item.seeds_remaining} remaining`}</span>
                          {item.queue_position !== null ? <span>{`Queue position ${item.queue_position}`}</span> : null}
                        </div>
                      </div>
                      <button
                        className="link-button secondary"
                        onClick={() => onOpenResults(item.results_path ? item.campaign_id : null)}
                        type="button"
                      >
                        {item.results_path ? "Results" : "Workspace"}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">
                  No active or recent persisted executions are visible yet. Use
                  Run Lab to launch the next canonical run.
                </p>
              )}
            </>
          )}
        </div>

        <div className="panel">
          <p className="eyebrow">Next step</p>
          <h2>Quick actions</h2>
          <div className="home-action-grid">
            <button className="link-button" onClick={onOpenRunLab} type="button">
              New run
            </button>
            <button className="link-button secondary" onClick={onOpenConfigs} type="button">
              Browse configs
            </button>
            <button className="link-button secondary" onClick={() => onOpenResults()} type="button">
              Open results
            </button>
            <button className="link-button secondary" onClick={onOpenCatalog} type="button">
              Open catalog
            </button>
            <button
              className="link-button secondary"
              onClick={onOpenDecisionPolicyAuthoring}
              type="button"
            >
              Create decision policy
            </button>
            <button
              className="link-button secondary"
              onClick={onOpenGenomeSchemaAuthoring}
              type="button"
            >
              Create genome schema
            </button>
            <button
              className="link-button secondary"
              onClick={onOpenMutationProfileAuthoring}
              type="button"
            >
              Create mutation profile
            </button>
            <button
              className="link-button secondary"
              onClick={onOpenSignalPackAuthoring}
              type="button"
            >
              Create signal pack
            </button>
          </div>
        </div>

        <div className="panel">
          <div className="results-panel-header">
            <div>
              <p className="eyebrow">Recent work</p>
              <h2>Recent campaigns</h2>
            </div>
            <button className="link-button secondary" onClick={() => onOpenResults()} type="button">
              All campaigns
            </button>
          </div>
          {isLoading ? (
            <p className="loading-text">Loading recent campaigns...</p>
          ) : recentCampaigns.length === 0 ? (
            <p className="muted">
              No campaigns have been persisted yet. After the first multiseed
              run completes, recent campaigns will show up here.
            </p>
          ) : (
            <div className="home-compact-list">
              {recentCampaigns.map((campaign) => (
                <div key={campaign.campaign_id} className="home-list-row">
                  <div className="home-list-row-main">
                    <strong className="primary-label">{campaign.config_name}</strong>
                    <div className="campaign-card-meta">
                      <span>{statusLabel(campaign.status)}</span>
                      <span>{campaign.dataset_label}</span>
                      <span>{formatDateTime(campaign.created_at)}</span>
                    </div>
                  </div>
                  <button
                    className="link-button secondary"
                    onClick={() => onOpenResults(campaign.campaign_id)}
                    type="button"
                  >
                    Open
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <p className="eyebrow">Reusable components</p>
          <h2>Library + authoring</h2>
          <p className="muted">
            Catalog is now the reusable component library. Run Lab stays focused
            on composing and launching runs, while Results stays focused on
            inspection and comparison.
          </p>
          <div className="home-library-grid">
            <div className="review-card">
              <span className="technical-meta-label">Catalog</span>
              <strong>Browse reusable components</strong>
            </div>
            <div className="review-card">
              <span className="technical-meta-label">Authoring now available</span>
              <strong>Mutation profiles and signal packs</strong>
            </div>
          </div>
          <div className="nav-actions">
            <button className="link-button secondary" onClick={onOpenCatalog} type="button">
              Open library
            </button>
            <button
              className="link-button secondary"
              onClick={onOpenMutationProfileAuthoring}
              type="button"
            >
              New mutation profile
            </button>
            <button
              className="link-button secondary"
              onClick={onOpenSignalPackAuthoring}
              type="button"
            >
              New signal pack
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
