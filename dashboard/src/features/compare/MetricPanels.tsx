import { motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { DESIGNS, ordered } from "../../lib/designs";
import { niceMax, num } from "../../lib/format";
import type { Metric, SplitResult } from "../../lib/types";
import { dur, ease, stagger } from "../../theme/motion";

// Small multiples: one panel per measure, one bar per design, each panel on its own axis from zero.

interface Tip {
  x: number;
  y: number;
  lines: string[];
  color: string;
}

export function MetricPanels({ result }: { result: SplitResult }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const reduce = useReducedMotion();
  const designs = ordered(result.designs);
  return (
    <>
      <div className="panels">
        {result.metrics.map((m: Metric, pi) => {
          const max = niceMax(Math.max(...designs.map((d) => d.metrics[m.key].mean + d.metrics[m.key].ci95)));
          const sub = m.better === "info" ? `${m.unit} · context, not a target` : `${m.unit} · ${m.better} is better`;
          return (
            <article className="panel" key={m.key}>
              <header>
                <h3 className="panel__title">{m.label}</h3>
                <p className="panel__sub">{sub}</p>
              </header>
              <div className="plot">
                <div className="grid" aria-hidden="true">
                  {[0, 0.5, 1].map((t) => (
                    <span key={t} className="grid__line" style={{ left: `${t * 100}%` }}>
                      <span className="grid__tick">{num(max * t)}</span>
                    </span>
                  ))}
                </div>
                <ul className="rows">
                  {designs.map((d, ri) => {
                    const s = d.metrics[m.key];
                    const meta = DESIGNS[d.design];
                    const lo = Math.max(0, (s.mean - s.ci95) / max);
                    const hi = Math.min(1, (s.mean + s.ci95) / max);
                    const show = (e: React.PointerEvent | React.FocusEvent) => {
                      const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
                      const x = "clientX" in e ? e.clientX : r.left + r.width / 2;
                      setTip({ x, y: r.top, color: meta.color,
                        lines: [meta.short, `${num(s.mean)} ± ${num(s.ci95)}`, m.unit] });
                    };
                    return (
                      <li
                        key={d.design}
                        className={d.design === "platform" ? "row row--hero" : "row"}
                        tabIndex={0}
                        aria-label={`${meta.short}: ${num(s.mean)} ± ${num(s.ci95)} ${m.unit}`}
                        onPointerEnter={show}
                        onPointerMove={show}
                        onPointerLeave={() => setTip(null)}
                        onFocus={show}
                        onBlur={() => setTip(null)}
                      >
                        <span className="row__label">
                          <span className="swatch" style={{ background: meta.color }} />
                          {meta.short}
                        </span>
                        <span className="row__track">
                          <motion.span
                            className="row__bar"
                            style={{ width: `${(s.mean / max) * 100}%`, background: meta.color, originX: 0 }}
                            initial={reduce ? false : { scaleX: 0 }}
                            animate={{ scaleX: 1 }}
                            transition={{ duration: dur.standard, ease: ease.out,
                              delay: Math.min((pi * 2 + ri) * stagger.step / 3, stagger.cap) }}
                          />
                          {s.ci95 > 0 && (
                            <span className="row__whisker" style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }} />
                          )}
                        </span>
                        <span className="row__value">{num(s.mean)}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </article>
          );
        })}
      </div>
      {tip && (
        <div className="tooltip" role="status" style={{ transform: `translate(${tip.x + 14}px, ${tip.y - 8}px)` }}>
          <div className="tooltip__head">
            <span className="swatch" style={{ background: tip.color }} />
            {tip.lines[0]}
          </div>
          <div className="tooltip__value">{tip.lines[1]}</div>
          <div className="tooltip__unit">{tip.lines[2]}</div>
        </div>
      )}
    </>
  );
}

export function CompareTable({ result }: { result: SplitResult }) {
  const designs = ordered(result.designs);
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th scope="col">Per year</th>
            {designs.map((d) => (
              <th scope="col" key={d.design}>
                <span className="swatch" style={{ background: DESIGNS[d.design].color }} />
                {DESIGNS[d.design].short}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.metrics.map((m) => (
            <tr key={m.key}>
              <th scope="row">
                {m.label} <span className="muted">({m.unit})</span>
              </th>
              {designs.map((d) => (
                <td key={d.design}>
                  {num(d.metrics[m.key].mean)} <span className="muted">± {num(d.metrics[m.key].ci95)}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
