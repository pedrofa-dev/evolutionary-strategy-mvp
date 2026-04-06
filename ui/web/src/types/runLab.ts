export type RunLabOptionClassification =
  | "active"
  | "internal_but_needed"
  | "legacy_but_still_required"
  | "example_only";

export type RunLabOption = {
  id: string;
  label: string;
  description: string | null;
  origin: "runtime" | "asset" | "plugin";
  classification: RunLabOptionClassification;
  selectable: boolean;
  warning: string | null;
  file_path: string | null;
  engine_name: string | null;
};

export type RunLabDatasetCatalogSummary = {
  id: string;
  description: string;
  market_type: string;
  timeframe: string;
  asset_symbols: string[];
  date_range_start: string;
  date_range_end: string;
  split_summary: Record<string, number>;
  sample_dataset_ids: Record<string, string[]>;
  file_path: string;
};

export type RunLabTemplateSummary = {
  id: string;
  label: string;
  file_path: string;
  dataset_catalog_id: string;
  signal_pack_name: string;
  genome_schema_name: string;
  decision_policy_name: string;
  mutation_profile_name: string;
  seed_mode: "range" | "explicit";
  seed_start: number | null;
  seed_count: number | null;
  explicit_seeds: number[];
  generations_planned: number;
};

export type RunLabBootstrap = {
  current_logic_version: string;
  dataset_catalogs: RunLabDatasetCatalogSummary[];
  signal_packs: RunLabOption[];
  genome_schemas: RunLabOption[];
  mutation_profiles: RunLabOption[];
  decision_policies: RunLabOption[];
  execution_presets: RunLabOption[];
  config_templates: RunLabTemplateSummary[];
  defaults: {
    template_config_name: string;
    dataset_catalog_id: string;
    signal_pack_name: string;
    genome_schema_name: string;
    mutation_profile_name: string;
    decision_policy_name: string;
    seed_mode: "range" | "explicit";
    seed_start: number | null;
    seed_count: number | null;
    explicit_seeds: number[];
    generations_planned: number;
    experiment_preset_name: string;
    parallel_workers: number;
    queue_concurrency_limit: number;
  };
};

export type RunLabSaveRequest = {
  template_config_name: string;
  config_name: string;
  dataset_catalog_id: string;
  signal_pack_name: string;
  genome_schema_name: string;
  mutation_profile_name: string;
  decision_policy_name: string;
  seed_mode: "range" | "explicit";
  seed_start: number | null;
  seed_count: number | null;
  explicit_seeds: string;
  parallel_workers?: number | null;
  queue_concurrency_limit?: number | null;
};

export type SavedRunConfigResult = {
  config_name: string;
  config_path: string;
  config_payload: Record<string, unknown>;
  warnings: string[];
};

export type MutationProfileAuthoringRequest = {
  id: string;
  description: string;
  strong_mutation_probability: number;
  numeric_delta_scale: number;
  flag_flip_probability: number;
  weight_delta: number;
  window_step_mode: string;
};

export type SavedMutationProfileAssetResult = {
  asset_id: string;
  asset_path: string;
  asset_payload: Record<string, unknown>;
};

export type SignalPackAuthoringRequest = {
  id: string;
  description: string;
  signals: string;
};

export type SavedSignalPackAssetResult = {
  asset_id: string;
  asset_path: string;
  asset_payload: Record<string, unknown>;
};

export type LaunchedRunResult = {
  saved_config: SavedRunConfigResult;
  job_id: string;
  launch_log_path: string;
  execution_configs_dir: string;
  campaign_id: string;
  status: string;
  preset_name: string | null;
  parallel_workers: number;
  queue_concurrency_limit: number;
  pid: number | null;
};
