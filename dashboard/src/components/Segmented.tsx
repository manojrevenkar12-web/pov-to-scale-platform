import { motion } from "framer-motion";
import { dur, ease } from "../theme/motion";

interface Props<T extends string> {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}

export function Segmented<T extends string>({ label, value, options, onChange }: Props<T>) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className="segment"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
        >
          {o.value === value && (
            <motion.span
              layoutId={`seg-${label}`}
              className="segment__pill"
              transition={{ duration: dur.quick, ease: ease.standard }}
            />
          )}
          <span className="segment__label">{o.label}</span>
        </button>
      ))}
    </div>
  );
}
