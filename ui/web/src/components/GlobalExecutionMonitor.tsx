import { useEffect, useMemo, useState } from "react";

import { cancelQueuedJob, getExecutionMonitorItems } from "../services/runsResultsApi";
import type { ExecutionMonitorItem } from "../types/results";

type GlobalExecutionMonitorProps = {
  onOpenResultsPath: (path: string) => void;
};

const DISMISSED_MONITOR_ITEMS_STORAGE_KEY = "dismissed-execution-monitor-items";

function sentenceCase(value: string): string {
  if (!value.trim()) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/[_-]+/g, " ");
}

function statusLabel(item: ExecutionMonitorItem): string {
  const normalized = item.status.trim().toLowerCase();
  if (normalized === "running") {
    return "Running";
  }
  if (normalized === "queued") {
    return "Queued";
  }
  if (normalized === "launching") {
    return "Launching";
  }
  if (normalized === "failed") {
    return "Failed";
  }
  if (normalized === "cancelled") {
    return "Cancelled";
  }
  if (normalized === "completed" || normalized === "finished") {
    return "Finished";
  }
  return sentenceCase(item.status);
}

function collapsedLabel(items: ExecutionMonitorItem[]): string {
  const runningCount = items.filter((item) => ["running", "launching"].includes(item.status)).length;
  const queuedCount = items.filter((item) => item.status === "queued").length;
  if (runningCount > 0 && queuedCount > 0) {
    return `${runningCount} running | ${queuedCount} queued`;
  }
  if (runningCount > 0) {
    return runningCount === 1 ? "1 run active" : `${runningCount} runs active`;
  }
  if (queuedCount > 0) {
    return queuedCount === 1 ? "1 run queued" : `${queuedCount} runs queued`;
  }
  return items.length === 1 ? "1 recent run" : `${items.length} recent runs`;
}

function isTerminalStatus(status: string): boolean {
  return ["finished", "completed", "failed", "cancelled"].includes(status.trim().toLowerCase());
}

function loadDismissedMonitorItems(): string[] {
  try {
    const rawValue = window.localStorage.getItem(DISMISSED_MONITOR_ITEMS_STORAGE_KEY);
    if (!rawValue) {
      return [];
    }
    const parsed = JSON.parse(rawValue) as unknown;
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function saveDismissedMonitorItems(jobIds: string[]) {
  window.localStorage.setItem(
    DISMISSED_MONITOR_ITEMS_STORAGE_KEY,
    JSON.stringify(jobIds),
  );
}

function formatSeedProgress(item: ExecutionMonitorItem): string {
  const finished = Math.max(item.seeds_finished, 0);
  const total = Math.max(item.seeds_total, 0);

  if (total <= 0) {
    return finished > 0 ? `${finished} seeds finished` : "Seed progress unavailable";
  }
  if (finished > total) {
    return `${finished} seeds finished`;
  }
  return `${finished} / ${total} seeds finished`;
}

export default function GlobalExecutionMonitor({
  onOpenResultsPath,
}: GlobalExecutionMonitorProps) {
  const [items, setItems] = useState<ExecutionMonitorItem[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancelInFlightJobId, setCancelInFlightJobId] = useState<string | null>(null);
  const [dismissedItemIds, setDismissedItemIds] = useState<string[]>([]);

  useEffect(() => {
    setDismissedItemIds(loadDismissedMonitorItems());
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadItems() {
      try {
        const nextItems = await getExecutionMonitorItems();
        if (!cancelled) {
          setItems(nextItems);
          setError(null);
          setHasLoadedOnce(true);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
          setHasLoadedOnce(true);
        }
      }
    }

    void loadItems();
    const intervalId = window.setInterval(() => {
      void loadItems();
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      };
  }, []);

  useEffect(() => {
    const activeIds = new Set(items.filter((item) => isTerminalStatus(item.status)).map((item) => item.job_id));
    const nextDismissedIds = dismissedItemIds.filter((jobId) => activeIds.has(jobId));
    if (nextDismissedIds.length !== dismissedItemIds.length) {
      setDismissedItemIds(nextDismissedIds);
      saveDismissedMonitorItems(nextDismissedIds);
    }
  }, [dismissedItemIds, items]);

  const visibleItems = useMemo(
    () =>
      items
        .filter((item) => !isTerminalStatus(item.status) || !dismissedItemIds.includes(item.job_id))
        .slice(0, 5),
    [dismissedItemIds, items],
  );
  const collapsedSummary = error && visibleItems.length === 0
    ? "Execution monitor unavailable"
    : !hasLoadedOnce
      ? "Loading runs..."
      : visibleItems.length > 0
        ? collapsedLabel(visibleItems)
        : "No active runs";

  function dismissItem(jobId: string) {
    const nextDismissedIds = [...new Set([...dismissedItemIds, jobId])];
    setDismissedItemIds(nextDismissedIds);
    saveDismissedMonitorItems(nextDismissedIds);
  }

  function clearDismissedItems() {
    setDismissedItemIds([]);
    saveDismissedMonitorItems([]);
  }

  async function handleCancelQueuedJob(jobId: string) {
    try {
      setCancelInFlightJobId(jobId);
      setError(null);
      await cancelQueuedJob(jobId);
      const nextItems = await getExecutionMonitorItems();
      setItems(nextItems);
      setHasLoadedOnce(true);
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Unknown error");
    } finally {
      setCancelInFlightJobId(null);
    }
  }

  return (
    <aside
      aria-live="polite"
      className={isExpanded ? "execution-monitor expanded" : "execution-monitor"}
    >
      <button
        className="execution-monitor-toggle"
        onClick={() => setIsExpanded((current) => !current)}
        type="button"
      >
        <span>{collapsedSummary}</span>
        <span>{isExpanded ? "Hide" : "Show"}</span>
      </button>

      {isExpanded ? (
        <div className="execution-monitor-body">
          {error ? (
            <div className="soft-warning">
              Monitor refresh failed. {error}
            </div>
          ) : null}

          {dismissedItemIds.length > 0 ? (
            <div className="execution-monitor-row">
              <div className="execution-monitor-row-main">
                <div className="execution-monitor-row-meta">
                  <span>{`${dismissedItemIds.length} dismissed terminal item${dismissedItemIds.length === 1 ? "" : "s"}`}</span>
                </div>
              </div>
              <div className="nav-actions">
                <button
                  className="link-button secondary execution-monitor-action"
                  onClick={clearDismissedItems}
                  type="button"
                >
                  Clear dismissed
                </button>
              </div>
            </div>
          ) : null}

          {!hasLoadedOnce && visibleItems.length === 0 ? (
            <div className="execution-monitor-row">
              <div className="execution-monitor-row-main">
                <div className="execution-monitor-row-topline">
                  <strong className="primary-label">Refreshing monitor</strong>
                </div>
                <div className="execution-monitor-row-meta">
                  <span>Checking canonical persisted run state.</span>
                </div>
              </div>
            </div>
          ) : null}

          {hasLoadedOnce && visibleItems.length === 0 && error === null ? (
            <div className="execution-monitor-row">
              <div className="execution-monitor-row-main">
                <div className="execution-monitor-row-topline">
                  <strong className="primary-label">No active runs</strong>
                  <span className="origin-tag origin-asset">Idle</span>
                </div>
                <div className="execution-monitor-row-meta">
                  <span>No active or recent persisted executions are available yet.</span>
                </div>
              </div>
            </div>
          ) : null}

          {hasLoadedOnce && visibleItems.length === 0 && error !== null ? (
            <div className="execution-monitor-row">
              <div className="execution-monitor-row-main">
                <div className="execution-monitor-row-topline">
                  <strong className="primary-label">Monitor unavailable</strong>
                </div>
                <div className="execution-monitor-row-meta">
                  <span>Results and Run Lab remain available.</span>
                </div>
              </div>
            </div>
          ) : null}

          {visibleItems.map((item) => (
            <div key={item.job_id} className="execution-monitor-row">
              <div className="execution-monitor-row-main">
                <div className="execution-monitor-row-topline">
                  <strong className="primary-label">{item.config_name}</strong>
                  <span className={item.is_active ? "origin-tag origin-runtime" : "origin-tag origin-asset"}>
                    {statusLabel(item)}
                  </span>
                </div>
                <div className="execution-monitor-row-meta">
                  <span>{formatSeedProgress(item)}</span>
                  <span>{`${item.seeds_remaining} remaining`}</span>
                  {item.queue_position !== null ? (
                    <span>{`Queue position ${item.queue_position}`}</span>
                  ) : null}
                </div>
              </div>
              <div className="nav-actions">
                {item.results_path ? (
                  <button
                    className="link-button secondary execution-monitor-action"
                    onClick={() => onOpenResultsPath(item.results_path!)}
                    type="button"
                  >
                    Results
                  </button>
                ) : null}
                {item.can_cancel ? (
                  <button
                    className="link-button secondary execution-monitor-action"
                    disabled={cancelInFlightJobId === item.job_id}
                    onClick={() => void handleCancelQueuedJob(item.job_id)}
                    type="button"
                  >
                    {cancelInFlightJobId === item.job_id ? "Cancelling..." : "Cancel"}
                  </button>
                ) : null}
                {isTerminalStatus(item.status) ? (
                  <button
                    className="link-button secondary execution-monitor-action"
                    onClick={() => dismissItem(item.job_id)}
                    type="button"
                  >
                    Dismiss
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </aside>
  );
}
