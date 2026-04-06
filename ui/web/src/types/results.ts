export type CampaignSummary = {
  campaign_id: string;
  multiseed_run_id: number;
  config_name: string;
  config_names: string[];
  dataset_label: string;
  dataset_catalog_ids: string[];
  preset_name: string | null;
  created_at: string;
  status: string;
  seeds_planned: number;
  seeds_completed: number;
  seeds_reused: number;
  runs_failed: number;
  mean_score: number | null;
  score_std_dev: number | null;
  champion_count: number;
  train_to_validation_survival_rate: number | null;
  validation_to_external_survival_rate: number | null;
  verdict: string | null;
  likely_limit: string | null;
  next_action: string | null;
  has_quick_summary: boolean;
  quick_summary_source: string | null;
  has_external_evaluation: boolean;
  external_artifact_available: boolean;
  has_champion: boolean;
  champion_classification: string | null;
};

export type CampaignExecution = {
  run_id: string;
  seed: number;
  status: string;
  train_score: number | null;
  validation_score: number | null;
  external_score: number | null;
  champion_classification: string | null;
  external_status: string | null;
  reuse_status: string | null;
  reuse_reason: string | null;
  reuse_reason_source: string | null;
};

export type ReuseOverview = {
  reused_count: number;
  fresh_success_count: number;
  failed_count: number;
  message: string;
  reason_scope_note: string;
};

export type EvaluationPanel = {
  train_mean_score: number | null;
  validation_mean_score: number | null;
  external_mean_score: number | null;
  selection_gap_mean: number | null;
  validation_score_std_dev: number | null;
  external_valid_count: number;
  external_positive_profit_count: number;
  external_rows_generated: number;
  external_status: string | null;
  has_external_evaluation: boolean;
  external_artifact_available: boolean;
};

export type CampaignChampion = {
  champion_id: number | null;
  classification: string | null;
  score: number | null;
  return_pct: number | null;
  drawdown: number | null;
  profit_factor: number | null;
  trades: number | null;
  stack_label: string | null;
  config_name: string | null;
  source: string | null;
  traceability: Record<string, unknown> | null;
};

export type CampaignDetail = {
  summary: CampaignSummary;
  champion: CampaignChampion | null;
  executions: CampaignExecution[];
  evaluation: EvaluationPanel;
  reuse_overview: ReuseOverview;
};

export type CampaignComparisonEntry = {
  campaign_id: string;
  config_name: string;
  dataset_label: string;
  mean_score: number | null;
  score_std_dev: number | null;
  train_to_validation_survival_rate: number | null;
  validation_to_external_survival_rate: number | null;
  champion_classification: string | null;
  champion_score: number | null;
  champion_return_pct: number | null;
  champion_drawdown: number | null;
  champion_trades: number | null;
  verdict: string | null;
  has_champion: boolean;
  has_external_evaluation: boolean;
  external_artifact_available: boolean;
  has_quick_summary: boolean;
};

export type ExecutionMonitorItem = {
  job_id: string;
  campaign_id: string;
  config_name: string;
  preset_name: string | null;
  launched_at: string;
  status: string;
  seeds_finished: number;
  seeds_total: number;
  seeds_remaining: number;
  seeds_running: number;
  requested_parallel_workers: number;
  effective_parallel_workers: number;
  generation_progress: string | null;
  results_path: string | null;
  is_recent: boolean;
  is_active: boolean;
  can_cancel: boolean;
  queue_position: number | null;
};

export type CancelledQueueJobResult = {
  job_id: string;
  campaign_id: string;
  status: string;
};

export type DeletedCampaignResult = {
  campaign_id: string;
  deleted_row_counts: Record<string, number>;
  deleted_artifact_paths: string[];
  missing_artifact_paths: string[];
  artifact_delete_failures: string[];
};
