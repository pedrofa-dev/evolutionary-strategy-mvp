import type {
  RunConfigBrowserSummary,
  RunConfigEditorView,
  RunConfigFileOperationResult,
} from "../types/configs";

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

export async function getConfigs(): Promise<RunConfigBrowserSummary[]> {
  const payload = await requestJson<{ items: RunConfigBrowserSummary[] }>("/api/configs");
  return payload.items;
}

export function getConfig(configName: string): Promise<RunConfigEditorView> {
  return requestJson<RunConfigEditorView>(`/api/configs/${encodeURIComponent(configName)}`);
}

export function duplicateConfig(
  sourceConfigName: string,
  newConfigName: string,
): Promise<RunConfigFileOperationResult> {
  return requestJson<RunConfigFileOperationResult>("/api/configs/duplicate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      source_config_name: sourceConfigName,
      new_config_name: newConfigName,
    }),
  });
}

export function renameConfig(
  sourceConfigName: string,
  newConfigName: string,
): Promise<RunConfigFileOperationResult> {
  return requestJson<RunConfigFileOperationResult>("/api/configs/rename", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      source_config_name: sourceConfigName,
      new_config_name: newConfigName,
    }),
  });
}

export function saveConfig(
  sourceConfigName: string,
  config: RunConfigEditorView,
): Promise<RunConfigEditorView> {
  return requestJson<RunConfigEditorView>("/api/configs/save", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      source_config_name: sourceConfigName,
      config,
    }),
  });
}

export function saveConfigAsNew(config: RunConfigEditorView): Promise<RunConfigEditorView> {
  return requestJson<RunConfigEditorView>("/api/configs/save-as-new", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      config,
    }),
  });
}
