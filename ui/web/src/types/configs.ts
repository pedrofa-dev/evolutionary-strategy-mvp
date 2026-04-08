export type ConfigRecentUsageSummary = {
  campaign_usage_count: number;
  latest_campaign_id: string | null;
  latest_campaign_started_at: string | null;
  latest_campaign_status: string | null;
  appears_in_persisted_executions: boolean;
};

export type RunConfigBrowserSummary = {
  config_name: string;
  config_path: string;
  dataset_catalog_id: string;
  signal_pack_name: string;
  genome_schema_name: string;
  decision_policy_name: string;
  mutation_profile_name: string;
  market_mode_name: string;
  leverage: number;
  seed_mode: string;
  seed_start: number | null;
  seed_count: number | null;
  explicit_seeds: number[];
  seed_summary: string;
  generations_planned: number;
  recent_usage: ConfigRecentUsageSummary;
};

export type ConfigIdentitySection = {
  config_name: string;
  config_path: string;
};

export type ConfigResearchStackSection = {
  dataset_catalog_id: string;
  signal_pack_name: string;
  genome_schema_name: string;
  decision_policy_name: string;
  mutation_profile_name: string;
  market_mode_name: string;
  leverage: number;
};

export type ConfigEvolutionBudgetSection = {
  mutation_seed: number;
  population_size: number;
  target_population_size: number;
  survivors_count: number;
  generations_planned: number;
};

export type ConfigSeedPlanSection = {
  mode: string;
  seed_start: number | null;
  seed_count: number | null;
  explicit_seeds: number[];
  summary: string;
};

export type ConfigEvaluationTradingSection = {
  trade_cost_rate: number;
  cost_penalty_weight: number;
  trade_count_penalty_weight: number;
  entry_score_margin: number;
  min_bars_between_entries: number;
  entry_confirmation_bars: number;
  regime_filter_enabled: boolean;
  min_trend_long_for_entry: number;
  min_breakout_for_entry: number;
  max_realized_volatility_for_entry: number | null;
};

export type ConfigAdvancedOverridesSection = {
  mutation_profile: Record<string, unknown>;
  entry_trigger: Record<string, unknown>;
  exit_policy: Record<string, unknown>;
  trade_control: Record<string, unknown>;
  entry_trigger_constraints: Record<string, unknown>;
};

export type RunConfigEditorView = {
  identity: ConfigIdentitySection;
  research_stack: ConfigResearchStackSection;
  evolution_budget: ConfigEvolutionBudgetSection;
  seed_plan: ConfigSeedPlanSection;
  evaluation_trading: ConfigEvaluationTradingSection;
  advanced_overrides: ConfigAdvancedOverridesSection;
  recent_usage: ConfigRecentUsageSummary;
};

export type RunConfigFileOperationResult = {
  config_name: string;
  config_path: string;
};
