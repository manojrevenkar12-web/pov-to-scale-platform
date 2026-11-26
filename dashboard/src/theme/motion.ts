// Motion tokens. Entrances decelerate, exits accelerate and are shorter.
export const ease = {
  out: [0.2, 0, 0, 1] as const,
  in: [0.4, 0, 1, 1] as const,
  standard: [0.4, 0, 0.2, 1] as const,
};

export const dur = {
  instant: 0.1,
  quick: 0.18,
  standard: 0.28,
  emphasised: 0.45,
};

export const stagger = { step: 0.04, cap: 0.4 };

export const rise = {
  hidden: { opacity: 0, y: 10 },
  shown: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: dur.standard, ease: ease.out, delay: Math.min(i * stagger.step, stagger.cap) },
  }),
};
