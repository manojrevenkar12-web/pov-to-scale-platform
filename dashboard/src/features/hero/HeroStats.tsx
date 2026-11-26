import { motion } from "framer-motion";
import { CountUp } from "../../components/CountUp";
import { byKey } from "../../lib/designs";
import { num } from "../../lib/format";
import type { SplitResult } from "../../lib/types";
import { rise } from "../../theme/motion";

const TILES = [
  { key: "isolation", title: "Client-data isolation incidents", unit: "per year", digits: 1 },
  { key: "overrun_keur", title: "Unapproved spend over budget", unit: "k€ per year", digits: 0 },
  { key: "bad_in_prod", title: "Regressed releases in production", unit: "per year", digits: 1 },
  { key: "env_days", title: "Days to a PoV environment", unit: "median", digits: 1 },
] as const;

export function HeroStats({ result }: { result: SplitResult }) {
  const d = byKey(result.designs);
  return (
    <div className="tiles">
      {TILES.map((t, i) => {
        const p = d.platform.metrics[t.key];
        const base = d.ad_hoc.metrics[t.key].mean;
        const shared = d.shared.metrics[t.key].mean;
        return (
          <motion.article className="tile" key={t.key} custom={i} variants={rise} initial="hidden" animate="shown">
            <h3 className="tile__title">{t.title}</h3>
            <p className="tile__value">
              <span className="tile__number">
                <CountUp value={p.mean} digits={t.digits} />
              </span>
              <span className="tile__ci">± {num(p.ci95)}</span>
            </p>
            <p className="tile__unit">Platform · {t.unit}</p>
            <p className="tile__compare">
              Hand-built <b>{num(base, t.digits)}</b> · shared subscription <b>{num(shared, t.digits)}</b>
            </p>
          </motion.article>
        );
      })}
    </div>
  );
}
