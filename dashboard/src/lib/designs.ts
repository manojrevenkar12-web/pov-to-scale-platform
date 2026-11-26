import type { DesignKey, DesignResult } from "./types";

// Each design keeps its colour everywhere: colour follows the entity, never its rank.
export const DESIGNS: Record<DesignKey, { short: string; color: string }> = {
  platform: { short: "Platform", color: "var(--series-platform)" },
  ad_hoc: { short: "Hand-built per PoV", color: "var(--series-adhoc)" },
  shared: { short: "One shared subscription", color: "var(--series-shared)" },
  platform_no_budgets: { short: "Platform, no budgets", color: "var(--series-nobudgets)" },
  platform_no_gate: { short: "Platform, no promotion gate", color: "var(--series-nogate)" },
};

export const ORDER: DesignKey[] = ["platform", "ad_hoc", "shared", "platform_no_budgets", "platform_no_gate"];

export function ordered(designs: DesignResult[]): DesignResult[] {
  return ORDER.map((k) => designs.find((d) => d.design === k)).filter((d): d is DesignResult => Boolean(d));
}

export function byKey(designs: DesignResult[]): Record<DesignKey, DesignResult> {
  return Object.fromEntries(designs.map((d) => [d.design, d])) as Record<DesignKey, DesignResult>;
}
