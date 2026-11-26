import { useCallback, useEffect, useState } from "react";
import type { Results } from "./types";

export type Load =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "empty" }
  | { status: "ready"; data: Results };

export function useResults(url = "data/results.json"): [Load, () => void] {
  const [state, setState] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    setState({ status: "loading" });
    fetch(url, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
        return (await r.json()) as Results;
      })
      .then((data) => {
        if (!alive) return;
        const has = (s: Results["dev"]) => Boolean(s && s.designs && s.designs.length);
        setState(has(data.heldout) || has(data.dev) ? { status: "ready", data } : { status: "empty" });
      })
      .catch((e: Error) => alive && setState({ status: "error", message: e.message }));
    return () => {
      alive = false;
    };
  }, [url, attempt]);

  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return [state, retry];
}
