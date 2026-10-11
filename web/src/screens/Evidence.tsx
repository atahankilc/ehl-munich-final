// Evidence: the PM's evidence library. Where every finding comes from (customer comments, the customer study, cited
// web research), which requirements use it, which customer themes no requirement covers yet, and which defect-led
// pain goes to quality instead of into requirements (D-038). Read-only — nothing here changes a requirement.
import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, qs } from "@/lib/api";
import type { FindingsPage, QualityPayload } from "@/lib/types";
import { useAppState } from "@/lib/hooks";
import { PageHead } from "@/components/Shell";
import { Seg } from "@/components/ui";
import { FindingsTab } from "./evidence/FindingsTab";
import { QualityTab } from "./evidence/QualityTab";
import { FindingDrawer } from "./evidence/FindingDrawer";
import "@/components/req.css";
import "./evidence.css";

type Tab = "findings" | "gaps" | "quality";
const TABS: Tab[] = ["findings", "gaps", "quality"];

/** All findings once, unfiltered — the vocabulary for the category filter and the tab counts. Local and cached. */
export function useFindingFacets() {
  return useQuery({
    queryKey: ["findings", "facets"],
    queryFn: () => api.get<FindingsPage>(`/api/findings${qs({ visible_only: false, limit: 2000 })}`),
    staleTime: 5 * 60_000,
  });
}

export default function Evidence() {
  const [params, setParams] = useSearchParams();
  const tab: Tab = TABS.includes(params.get("tab") as Tab) ? (params.get("tab") as Tab) : "findings";
  const openId = params.get("f") ? Number(params.get("f")) : null;

  const setParam = useCallback(
    (patch: Record<string, string | null>, replace = true) => {
      setParams(
        (p) => {
          const n = new URLSearchParams(p);
          for (const [k, v] of Object.entries(patch)) {
            if (v === null || v === "") n.delete(k);
            else n.set(k, v);
          }
          return n;
        },
        { replace },
      );
    },
    [setParams],
  );

  const { data: state } = useAppState();
  const facets = useFindingFacets();
  const quality = useQuery({ queryKey: ["quality", "", ""], queryFn: () => api.get<QualityPayload>("/api/quality") });

  const counts = useMemo(() => {
    const w = state?.current_wave ?? 0;
    const items = facets.data?.items ?? [];
    const visible = w ? items.filter((f) => (f.first_wave ?? 1) <= w) : items;
    return {
      findings: facets.data ? visible.length : undefined,
      gaps: facets.data ? visible.filter((f) => f.n_requirements === 0 && f.polarity === "pain_or_want").length : undefined,
      quality: quality.data?.n_issues,
    };
  }, [facets.data, quality.data, state?.current_wave]);

  const lede =
    tab === "gaps"
      ? "Customer themes no requirement cites yet — candidates for the next wave."
      : tab === "quality"
        ? "Pain that is mostly defects goes to the quality teams, not into requirements. This is the hand-over list."
        : "Every finding the requirements stand on — where it comes from, how loud it is per market, and who uses it.";

  return (
    <main className="page evidence">
      <PageHead
        title="Evidence"
        lede={lede}
        actions={
          <Seg<Tab>
            label="Evidence view"
            value={tab}
            onChange={(v) => setParam({ tab: v === "findings" ? null : v, f: null, n: null }, false)}
            options={[
              { value: "findings", label: "Findings", count: counts.findings },
              { value: "gaps", label: "Gaps", count: counts.gaps },
              { value: "quality", label: "Quality hand-over", count: counts.quality },
            ]}
          />
        }
      />

      {tab === "quality" ? (
        <QualityTab params={params} setParam={setParam} categories={categoriesOf(facets.data)} />
      ) : (
        <FindingsTab
          key={tab}
          mode={tab}
          params={params}
          setParam={setParam}
          categories={categoriesOf(facets.data)}
          onOpen={(id) => setParam({ f: String(id) }, false)}
          openId={openId}
        />
      )}

      <FindingDrawer id={openId} onClose={() => setParam({ f: null })} />
    </main>
  );
}

function categoriesOf(p: FindingsPage | undefined): string[] {
  if (!p) return [];
  return [...new Set(p.items.map((f) => f.category).filter((c): c is string => !!c))].sort();
}
