import { motion } from "framer-motion";
import { DESIGNS, byKey } from "../../lib/designs";
import { num } from "../../lib/format";
import type { SplitResult } from "../../lib/types";
import { rise } from "../../theme/motion";

// What each safeguard buys, and what the platform costs: the same years with one part switched off.
export function Ablations({ result }: { result: SplitResult }) {
  const d = byKey(result.designs);
  const p = d.platform.metrics;
  const cards = [
    {
      key: "platform_no_budgets" as const,
      title: "Without budgets",
      figure: `€${num(d.platform_no_budgets.metrics.overrun_keur.mean, 0)}k`,
      body: "unapproved spend a year from runaway agents and leaked keys, caught only at the monthly invoice.",
    },
    {
      key: "platform_no_gate" as const,
      title: "Without the promotion gate",
      figure: num(d.platform_no_gate.metrics.bad_in_prod.mean),
      body: `regressed releases a year reach production, instead of ${num(p.bad_in_prod.mean)}; the gate sends back ${num(p.gate_stops.mean)} releases, about a week each.`,
    },
    {
      key: "platform" as const,
      title: "What the platform costs",
      figure: `${num(p.blocked_days.mean, 0)} days`,
      body: `a year in which a PoV waited for its owner to raise a budget, plus running the platform (in the ${num(p.engineer_hours.mean, 0)} engineer hours).`,
    },
  ];
  return (
    <div className="ablations">
      {cards.map((c, i) => (
        <motion.article key={c.title} className="ablation" custom={i} variants={rise} initial="hidden" animate="shown"
          style={{ borderTopColor: DESIGNS[c.key].color }}>
          <h3 className="ablation__title">{c.title}</h3>
          <p className="ablation__figure">{c.figure}</p>
          <p className="ablation__body">{c.body}</p>
        </motion.article>
      ))}
    </div>
  );
}
