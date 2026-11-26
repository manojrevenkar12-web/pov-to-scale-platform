import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";
import { num } from "../lib/format";
import { dur, ease } from "../theme/motion";

// Numbers count up once when they arrive, so a change of split reads as a change.
export function CountUp({ value, digits = 1 }: { value: number; digits?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (reduce) {
      node.textContent = num(value, digits);
      return;
    }
    const controls = animate(0, value, {
      duration: dur.emphasised * 2,
      ease: ease.out,
      onUpdate: (v) => (node.textContent = num(v, digits)),
    });
    return () => controls.stop();
  }, [value, digits, reduce]);
  return <span ref={ref}>{num(value, digits)}</span>;
}
