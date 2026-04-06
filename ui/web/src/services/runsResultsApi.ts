import type {
  CancelledQueueJobResult,
  CampaignComparisonEntry,
  CampaignDetail,
  CampaignSummary,
  DeletedCampaignResult,
  ExecutionMonitorItem,
} from "../types/results";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const contentType = response.headers.get("content-type") ?? "";

  if (!response.ok) {
    const errorBody = await response.text();
    let detail = errorBody;

    try {
      const parsed = JSON.parse(errorBody) as { message?: string; error?: string };
      detail = parsed.message ?? parsed.error ?? errorBody;
    } catch {
      detail = errorBody;
    }

    throw new Error(`Request failed (${response.status}): ${detail}`);
  }

  if (!contentType.toLowerCase().includes("application/json")) {
    const unexpectedBody = await response.text();
    throw new Error(
      `Expected JSON from ${path}, received ${contentType || "unknown content-type"}: ${unexpectedBody.slice(0, 160)}`,
    );
  }

  return (await response.json()) as T;
}

export async function getCampaigns(): Promise<CampaignSummary[]> {
  const response = await requestJson<{ campaigns: CampaignSummary[] }>("/runs/campaigns");
  return response.campaigns;
}

export function getCampaignDetail(campaignId: string): Promise<CampaignDetail> {
  return requestJson<CampaignDetail>(`/runs/campaign/${encodeURIComponent(campaignId)}`);
}

export async function compareCampaigns(
  campaignIds: string[],
): Promise<CampaignComparisonEntry[]> {
  const ids = campaignIds.map((id) => encodeURIComponent(id)).join(",");
  const response = await requestJson<{ items: CampaignComparisonEntry[] }>(
    `/runs/compare?ids=${ids}`,
  );
  return response.items;
}

export async function getExecutionMonitorItems(): Promise<ExecutionMonitorItem[]> {
  const response = await requestJson<{ items: ExecutionMonitorItem[] }>("/runs/monitor");
  return response.items;
}

export function deleteCampaign(campaignId: string): Promise<DeletedCampaignResult> {
  return requestJson<DeletedCampaignResult>(
    `/runs/campaign/${encodeURIComponent(campaignId)}`,
    {
      method: "DELETE",
    },
  );
}

export function cancelQueuedJob(jobId: string): Promise<CancelledQueueJobResult> {
  return requestJson<CancelledQueueJobResult>(
    `/runs/jobs/${encodeURIComponent(jobId)}/cancel`,
    {
      method: "POST",
    },
  );
}
