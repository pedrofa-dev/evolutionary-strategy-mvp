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
};

export type SavedRunConfigResult = {
  config_name: string;
  config_path: string;
  config_payload: Record<string, unknown>;
  warnings: string[];
};

export type LaunchedRunResult = {
  saved_config: SavedRunConfigResult;
  command: string[];
  launch_log_path: string;
  execution_configs_dir: string;
  pid: number;
  preset_name: string | null;
};
