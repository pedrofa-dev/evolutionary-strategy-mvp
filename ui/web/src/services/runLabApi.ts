import type {
  LaunchedRunResult,
  RunLabBootstrap,
  RunLabSaveRequest,
  SavedRunConfigResult,
} from "../types/runLab";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Request failed (${response.status}): ${errorBody}`);
  }

  return (await response.json()) as T;
}

export function getRunLabBootstrap(): Promise<RunLabBootstrap> {
  return requestJson<RunLabBootstrap>("/run-lab");
}

export function saveRunConfig(request: RunLabSaveRequest): Promise<SavedRunConfigResult> {
  return requestJson<SavedRunConfigResult>("/run-lab/configs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function saveAndExecuteRun(
  request: RunLabSaveRequest & { experiment_preset_name: string | null },
): Promise<LaunchedRunResult> {
  return requestJson<LaunchedRunResult>("/run-lab/executions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}
