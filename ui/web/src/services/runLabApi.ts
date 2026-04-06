import type {
  LaunchedRunResult,
  MutationProfileAuthoringRequest,
  RunLabBootstrap,
  RunLabSaveRequest,
  SavedSignalPackAssetResult,
  SavedMutationProfileAssetResult,
  SavedRunConfigResult,
  SignalPackAuthoringRequest,
} from "../types/runLab";

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

export function saveMutationProfileAsset(
  request: MutationProfileAuthoringRequest,
): Promise<SavedMutationProfileAssetResult> {
  return requestJson<SavedMutationProfileAssetResult>(
    "/run-lab/authoring/mutation-profiles",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export function saveSignalPackAsset(
  request: SignalPackAuthoringRequest,
): Promise<SavedSignalPackAssetResult> {
  return requestJson<SavedSignalPackAssetResult>(
    "/run-lab/authoring/signal-packs",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}
