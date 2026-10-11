import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { AppState, Meta } from "./types";

export const useMeta = () => useQuery({ queryKey: ["meta"], queryFn: () => api.get<Meta>("/api/meta"), staleTime: Infinity });

export const useAppState = () =>
  useQuery({
    queryKey: ["state"],
    queryFn: () => api.get<AppState>("/api/state"),
    refetchInterval: (q) => (q.state.data?.running_job ? 2500 : 30_000),
  });
