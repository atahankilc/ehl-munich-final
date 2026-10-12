// Page 4 inspector: WHAT the PM decides on (the requirement as page 3 defined it: statement, area, metric, the rung in
// use for this line × market, acceptance) and the bundle as rows (title, target value here, own score and band, the
// band the bundle lifted it to). Data from page 3's endpoints (cached react-query hooks), nothing new stored.
import { useLocation, useNavigate } from "react-router-dom";
import type { PrioBundle, Target } from "@/lib/prioritize";
import type { LadderRow, Level, LineName, Requirement } from "@/lib/definition";
import { setTopPanel } from "@/components/topPanel";
import { domainColor, useDefinition, useRequirementDetail } from "../definition/data";
import { setView } from "../definition/store";
import { BandMark } from "./marks";
import { pmBand, shownBand } from "./data";
import { selectTarget } from "./store";

const DIR: Record<string, string> = { higher: "higher is better", lower: "lower is better", binary: "yes / no" };
const BASIS: Record<string, string> = { cited: "cited", projected: "projected", assumption: "assumption", gap: "evidence gap" };
const RUNG_NAME: Record<string, string> = { baseline: "Baseline", threshold: "Threshold", target: "Target", stretch: "Stretch" };
const fmt = (n: number) => Math.round(n).toLocaleString("en-US");

const rowOf = (r: Pick<Requirement, "ladder"> | null | undefined, line: string, market: string): LadderRow | null =>
  r?.ladder?.find((x) => x.line === line && x.market === market) ?? null;
const levelOf = (row: LadderRow | null, rung: string | null | undefined): Level | null =>
  row && rung ? ((row as unknown as Record<string, Level | null>)[rung] ?? null) : null;

export function Deciding({ t }: { t: Target }) {
  const def = useDefinition();
  const r = useRequirementDetail(t.key, def);
  const navigate = useNavigate();
  const { search } = useLocation();
  if (!r) return null;
  const row = rowOf(r, t.line, t.market);
  const rung = row?.choice?.level ?? t.rung.chosen ?? t.rung.recommended;
  const lv = levelOf(row, rung);
  const by = row?.choice ? `PM chose ${rung}` : t.rung.by === "pm" ? `PM chose ${rung}` : `AI recommends ${rung}`;
  const open = () => {
    setTopPanel("requirements");
    setView({ line: t.line as LineName, selected: t.key });
    navigate(`/definition${search}`);
  };
  return (
    <div className="dblock pdeciding">
      <span className="label">What you're deciding on</span>
      <p className="pdeciding-statement">{r.statement}</p>
      <dl className="pdeciding-facts">
        {r.area_title && <><dt className="label">From area</dt><dd>{r.area_title}</dd></>}
        {r.metric && <><dt className="label">Metric</dt><dd>{r.metric.name}<span className="label"> · {r.metric.unit} · {DIR[r.metric.direction] ?? r.metric.direction}</span></dd></>}
        <dt className="label">In {t.line} · {t.market}</dt>
        <dd>{RUNG_NAME[rung] ?? rung} {lv?.text || (lv?.value != null ? String(lv.value) : "–")}
          <span className="label"> · {lv ? BASIS[lv.basis] ?? lv.basis : "no value"} · {by}</span></dd>
      </dl>
      {r.acceptance?.length > 0 && (
        <ul className="drail pdeciding-acc">
          {r.acceptance.slice(0, 3).map((a, i) => <li key={i}><b>{a.criterion}</b> · {a.pass}</li>)}
        </ul>
      )}
      <button className="dtext" onClick={open}>View definition →</button>
    </div>
  );
}

export function BundleMembers({ t, bundle, targets }: { t: Target; bundle: PrioBundle; targets: Target[] }) {
  const def = useDefinition();
  const reqs = new Map(def.notRun ? [] : def.data.requirements.map((r) => [r.key, r]));
  return (
    <ul className="pmembers pmembers-rows">
      {bundle.keys.map((k) => {
        const o = targets.find((x) => x.key === k && x.line === t.line && x.market === t.market);
        const req = reqs.get(k);
        const title = o?.title ?? req?.title ?? k;
        if (!o) return <li key={k}><span className="dlink-other pmembers-off">{title} <span className="label">not targeted in {t.market}</span></span></li>;
        const row = rowOf(req, t.line, t.market);
        const lv = levelOf(row, row?.choice?.level ?? o.rung.chosen ?? o.rung.recommended);
        const own = o.own_band ?? null;
        const band = shownBand(o);
        return (
          <li key={k}>
            <button className="pmember" aria-current={k === t.key ? "true" : undefined} onClick={() => selectTarget(k)}>
              <BandMark band={band} color={domainColor(o.domain)} size="sm" pm={!!pmBand(o)} />
              <span className="pmember-title">{title}</span>
              <span className="pmembers-s">{fmt(o.score)}</span>
              <span className="pmember-sub label">
                {lv?.text ? `${lv.text} · ` : ""}{own && own !== o.band ? `scores ${own} alone · lifted to ${o.band} by the bundle` : `${o.band} on its own score`}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
