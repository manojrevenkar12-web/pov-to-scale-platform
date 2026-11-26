import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Segmented } from "./components/Segmented";
import { EmptyState, ErrorState, Skeleton } from "./components/States";
import { Ablations } from "./features/ablations/Ablations";
import { CompareTable, MetricPanels } from "./features/compare/MetricPanels";
import { HeroStats } from "./features/hero/HeroStats";
import { Journey } from "./features/journey/Journey";
import type { SplitResult } from "./lib/types";
import { useResults } from "./lib/useResults";
import { dur, ease } from "./theme/motion";

type Split = "heldout" | "dev";
type View = "chart" | "table";

export default function App() {
  const [load, retry] = useResults();
  const [split, setSplit] = useState<Split | null>(null);
  const [view, setView] = useState<View>("chart");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const theme = params.get("theme");
    if (theme) document.documentElement.dataset.theme = theme;
  }, []);

  const data = load.status === "ready" ? load.data : null;
  const available: Split[] = data ? (["heldout", "dev"] as Split[]).filter((s) => data[s]) : [];
  const active = split && available.includes(split) ? split : available[0];
  const result: SplitResult | null = data && active ? data[active] : null;

  return (
    <main className="page" data-status={load.status}>
      <header className="masthead">
        <div>
          <p className="eyebrow">pov-to-scale-platform · 12-month lab</p>
          <h1 className="title">Ninety-six client PoVs a year, five ways to run them</h1>
          <p className="lede">
            The same engagements and the same luck under every design: hand-built environments through an IT
            ticket, one shared subscription, and the platform with and without its budgets and promotion gate.
            The platform designs run the real policy, budget and promotion-gate code.
          </p>
          <p className="scope">
            {result
              ? `${result.seeds.length} simulated years × ${result.engagements_per_year} engagements · seeds ${result.seeds[0]}–${result.seeds.at(-1)} · settings ${result.config_sha256.slice(0, 12)}`
              : " "}
          </p>
        </div>
        <div className="controls">
          {available.length > 0 && (
            <Segmented
              label="Seed split"
              value={active}
              onChange={(v) => setSplit(v)}
              options={available.map((s) => ({ value: s, label: s === "heldout" ? "Held-out years" : "Dev years" }))}
            />
          )}
          <button
            type="button"
            className="button button--quiet"
            onClick={() => {
              const root = document.documentElement;
              const dark = root.dataset.theme
                ? root.dataset.theme === "dark"
                : matchMedia("(prefers-color-scheme: dark)").matches;
              root.dataset.theme = dark ? "light" : "dark";
            }}
          >
            Light / dark
          </button>
        </div>
      </header>

      {load.status === "error" && <ErrorState message={load.message} onRetry={retry} />}
      {load.status === "empty" && <EmptyState />}

      {(load.status === "loading" || result) && (
        <AnimatePresence mode="wait">
          <motion.div
            key={active ?? "loading"}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { duration: dur.quick, ease: ease.out } }}
            exit={{ opacity: 0, transition: { duration: dur.instant, ease: ease.in } }}
          >
            <section className="section" aria-labelledby="h-hero">
              <h2 className="section__title" id="h-hero">The platform against the two usual set-ups</h2>
              {result ? <HeroStats result={result} /> : <div className="tiles">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="tile" />)}</div>}
            </section>

            <section className="section" aria-labelledby="h-journey">
              <h2 className="section__title" id="h-journey">An engagement's path on the platform</h2>
              <p className="section__note">What each step did in an average simulated year.</p>
              {result ? <Journey result={result} /> : <Skeleton className="journey-skeleton" />}
            </section>

            <section className="section" aria-labelledby="h-compare">
              <div className="section__bar">
                <h2 className="section__title" id="h-compare">Every measure, per design</h2>
                <Segmented
                  label="View"
                  value={view}
                  onChange={setView}
                  options={[
                    { value: "chart", label: "Charts" },
                    { value: "table", label: "Table" },
                  ]}
                />
              </div>
              <p className="section__note">
                Mean per simulated year; the whisker is the 95% interval across years. Each panel has its own scale from zero.
              </p>
              {result ? (
                view === "chart" ? <MetricPanels result={result} /> : <CompareTable result={result} />
              ) : (
                <div className="panels">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="panel" />)}</div>
              )}
            </section>

            <section className="section" aria-labelledby="h-ablations">
              <h2 className="section__title" id="h-ablations">What each safeguard buys, and what it costs</h2>
              {result ? <Ablations result={result} /> : <Skeleton className="panel" />}
            </section>
          </motion.div>
        </AnimatePresence>
      )}

      <footer className="footer">
        Every rate behind these numbers is an assumption in <code>config/lab.yaml</code>. The lab compares designs on the
        same luck; it does not measure any real firm's engagements. Generated by <code>pts lab report</code>.
      </footer>
    </main>
  );
}
