import { useEffect, useState, useSyncExternalStore } from "react";

export function useRemote<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
) {
  const [state, setState] = useState<{ key: string; data?: T; error?: Error }>({
    key: "",
  });
  useEffect(() => {
    const controller = new AbortController();
    void fetcher(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ key, data });
      },
      (error) => {
        if (!controller.signal.aborted)
          setState({
            key,
            error:
              error instanceof Error ? error : new Error("Error de conexión"),
          });
      },
    );
    return () => controller.abort();
  }, [key, fetcher]);
  return state.key === key
    ? { ...state, loading: false }
    : { data: undefined, error: undefined, loading: true };
}
const subscribe = (callback: () => void) => {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
};
export function useRoute() {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash);
  const [path, query] = (hash.slice(1) || "/overview").split("?");
  return { page: path, params: new URLSearchParams(query) };
}
export const explorerLink = (id: string, caseId?: string) =>
  `#/explorer?run=${encodeURIComponent(id)}${caseId ? `&case=${encodeURIComponent(caseId)}` : ""}`;
