export function num(x: number | undefined, digits = 1): string {
  if (x === undefined || Number.isNaN(x)) return "–";
  if (Math.abs(x) >= 1000) return Math.round(x).toLocaleString("en");
  const s = x.toFixed(digits);
  return s.endsWith(".0") ? s.slice(0, -2) : s;
}

export function niceMax(x: number): number {
  if (x <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(x));
  const f = x / exp;
  const step = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return step * exp;
}
