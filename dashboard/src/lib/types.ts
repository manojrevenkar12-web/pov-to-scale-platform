export interface Stat {
  mean: number;
  ci95: number;
}

export interface Metric {
  key: string;
  label: string;
  unit: string;
  better: "lower" | "higher" | "info";
}

export interface DesignResult {
  design: DesignKey;
  label: string;
  metrics: Record<string, Stat>;
}

export interface SplitResult {
  split: "dev" | "heldout";
  seeds: number[];
  engagements_per_year: number;
  config_sha256: string;
  metrics: Metric[];
  designs: DesignResult[];
}

export interface Results {
  dev: SplitResult | null;
  heldout: SplitResult | null;
}

export type DesignKey = "platform" | "ad_hoc" | "shared" | "platform_no_budgets" | "platform_no_gate";
