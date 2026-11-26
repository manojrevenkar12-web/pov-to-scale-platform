import { motion } from "framer-motion";
import { byKey } from "../../lib/designs";
import { num } from "../../lib/format";
import type { SplitResult } from "../../lib/types";
import { rise } from "../../theme/motion";

// The path an engagement takes on the platform, with what each step did over the year.
export function Journey({ result }: { result: SplitResult }) {
  const p = byKey(result.designs).platform.metrics;
  const steps = [
    { name: "Request", note: "plain words to the provisioning agent", figure: `${result.engagements_per_year}`, unit: "PoVs a year" },
    { name: "Policy check", note: "region, models, budget, consent", figure: num(p.policy_blocks.mean), unit: "stopped and fixed" },
    { name: "Pull request", note: "one approval; Terraform plan in CI", figure: num(p.env_days.mean), unit: "days to environment" },
    { name: "AI gateway", note: "budgets, isolation, redaction", figure: num(p.blocked_days.mean, 0), unit: "days waiting on a budget" },
    { name: "Promotion gate", note: "SLOs, eval, cost per 1k requests", figure: num(p.gate_stops.mean), unit: "releases sent back" },
    { name: "Scaled", note: "same artefacts, burn-rate alerts", figure: num(p.weeks_to_scaled.mean), unit: "weeks PoV end to go-live" },
  ];
  return (
    <ol className="journey">
      {steps.map((s, i) => (
        <motion.li key={s.name} className="journey__step" custom={i} variants={rise} initial="hidden" animate="shown">
          <span className="journey__index">{String(i + 1).padStart(2, "0")}</span>
          <h3 className="journey__name">{s.name}</h3>
          <p className="journey__note">{s.note}</p>
          <p className="journey__figure">{s.figure}</p>
          <p className="journey__unit">{s.unit}</p>
        </motion.li>
      ))}
    </ol>
  );
}
