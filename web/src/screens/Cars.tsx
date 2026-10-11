// Cars: today's car in a 3D studio, with the successor's recommended requirements pinned where customers
// experience them. Pick a market: the pins, the list and the priorities change — markets are different customers.
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, ChevronRight, Scale, X } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { CarPayload, CarRequirement, Priority } from "@/lib/types";
import { CAR, KANO, MARKET, PRIORITIES } from "@/lib/labels";
import { ErrorNote, EvidenceMeter, PriorityMark, ScoreBar, Seg, SkeletonBlock } from "@/components/ui";
import type { Hotspot } from "@/three/CarStage";
import "./cars.css";

const CarStage = lazy(() => import("@/three/CarStage"));
const VEHICLES = ["F70", "G60", "G68", "G70"];
const PRI_RANK: Record<Priority, number> = { Must: 0, Should: 1, Could: 2 };
const AVAIL: Record<string, string> = { standard: "Standard", optional: "Option", package: "In a package" };

export default function Cars() {
  const { vehicle } = useParams();
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const market = sp.get("market") ?? "";
  const zone = sp.get("zone");
  const q = useQuery({
    queryKey: ["car", vehicle, market],
    queryFn: () => api.get<CarPayload>(`/api/cars/${vehicle}${qs({ market })}`),
    enabled: !!vehicle,
    placeholderData: (prev) => (prev && prev.vehicle === vehicle ? prev : undefined),
  });
  const [hover, setHover] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const d = q.data;

  useEffect(() => setOpen(null), [vehicle, market]);

  const setParam = (k: string, v: string | null) =>
    setSp((p) => {
      if (v) p.set(k, v);
      else p.delete(k);
      return p;
    }, { replace: true });

  const hotspots: Hotspot[] = useMemo(() => {
    if (!d) return [];
    const by = new Map<string, Hotspot>();
    for (const r of d.requirements) {
      const h = by.get(r.zone) ?? { zone: r.zone, count: 0, top: "Could" as Priority, aiOnly: true };
      h.count += 1;
      if (PRI_RANK[r.priority] < PRI_RANK[h.top]) h.top = r.priority;
      h.aiOnly = h.aiOnly && r.ai_only;
      by.set(r.zone, h);
    }
    return [...by.values()];
  }, [d]);

  const list = d ? d.requirements.filter((r) => !zone || r.zone === zone) : [];
  const must = d?.requirements.filter((r) => r.priority === "Must").length ?? 0;
  if (!vehicle) return <Navigate to="/cars/G60?market=US" replace />;

  return (
    <main className="page carspage">
      <div className="cars-bar">
        <Seg label="Car" value={vehicle} onChange={(v) => nav(`/cars/${v}`)} options={VEHICLES.map((v) => ({ value: v, label: CAR[v] }))} />
        {d && (
          <Seg
            label="Market"
            value={d.market}
            onChange={(m) => setParam("market", m)}
            options={d.markets.map((m) => ({ value: m.market, label: m.label, count: m.n }))}
          />
        )}
      </div>

      {q.isError && <ErrorNote error={q.error} onRetry={() => q.refetch()} />}

      <section className="stage-wrap">
        <div className="stage">
          {d && (
            <Suspense fallback={<div className="stage-loading" />}>
              <CarStage
                modelUrl={d.model.url}
                orientation={d.model.orientation as never}
                zones={d.zones}
                hotspots={hotspots}
                selectedZone={zone}
                onSelectZone={(z) => setParam("zone", z)}
                hoverZone={hover}
              />
            </Suspense>
          )}
          {d && (
            <div className="stage-hud">
              <h1 className="stage-title">{d.car}</h1>
              <p className="stage-sub">
                {MARKET[d.market] ?? d.market} · <b>{d.requirements.length}</b> recommendations for the successor · <b>{must}</b> Must
              </p>
            </div>
          )}
          {d && (
            <div className="stage-tools">
              {d.configurator_url && (
                <a className="btn btn-sm" href={d.configurator_url} target="_blank" rel="noreferrer" title="Today's car in BMW's public configurator (Germany)">
                  Today's car in the configurator <ArrowUpRight />
                </a>
              )}
            </div>
          )}
          {d && d.model.url && (
            <div className="stage-credit">
              3D model “{d.model.attribution.name}” by {d.model.attribution.author} · {d.model.attribution.license} ·{" "}
              <a href={d.model.attribution.source_url} target="_blank" rel="noreferrer">Sketchfab</a>
              {d.model.shared_with && <> · shown on the {CAR[d.model.shared_with]} model</>}
            </div>
          )}
        </div>

        <aside className="stage-list" aria-label="Recommendations">
          <div className="sl-head">
            <div>
              <div className="sl-title">{zone && d ? d.zones[zone]?.label ?? zone : "Whole car"}</div>
              <div className="t-small muted">{list.length} recommendation{list.length === 1 ? "" : "s"}</div>
            </div>
            {zone && (
              <button className="btn btn-sm btn-ghost" onClick={() => setParam("zone", null)}>
                <X /> Whole car
              </button>
            )}
          </div>
          <div className="sl-body">
            {q.isLoading && <SkeletonBlock lines={8} />}
            {PRIORITIES.map((p) => {
              const rs = list.filter((r) => r.priority === p);
              if (!rs.length) return null;
              return (
                <section key={p} className="sl-group">
                  <h2 className="sl-gh">
                    <PriorityMark p={p} size="sm" /> <span className="faint num">{rs.length}</span>
                  </h2>
                  {rs.map((r) => (
                    <ReqRow
                      key={r.id}
                      r={r}
                      open={open === r.id}
                      zoneLabel={d?.zones[r.zone]?.label ?? r.zone}
                      onHover={(h) => setHover(h ? r.zone : null)}
                      onClick={() => {
                        setOpen(open === r.id ? null : r.id);
                        if (r.zone !== zone) setParam("zone", r.zone);
                      }}
                      market={d!.market}
                      targetKey={`${d!.vehicle}×${d!.market}`}
                    />
                  ))}
                </section>
              );
            })}
            {zone && d && <Equipment items={d.equipment[zone] ?? []} note={d.equipment_note} />}
          </div>
        </aside>
      </section>

      {d && <Comparison d={d} />}
      {d && <MarketContext d={d} />}
    </main>
  );
}

function ReqRow({ r, open, onClick, onHover, zoneLabel, market, targetKey }: { r: CarRequirement; open: boolean; onClick: () => void; onHover: (h: boolean) => void; zoneLabel: string; market: string; targetKey: string }) {
  return (
    <div className={`sl-item${open ? " open" : ""}`} onMouseEnter={() => onHover(true)} onMouseLeave={() => onHover(false)}>
      <button className="sl-row" onClick={onClick} aria-expanded={open}>
        <span className="sl-row-title">{r.title}</span>
        <span className="sl-row-meta">
          <span className="faint">{zoneLabel}</span>
          <ScoreBar score={r.score} width={44} />
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }} className="sl-more">
            <div className="sl-more-in">
              {r.product_decision ? <p className="sl-ask">{r.product_decision}</p> : r.description && <p className="sl-desc">{r.description}</p>}
              <div className="row wrap" style={{ gap: 6 }}>
                <PriorityMark p={r.priority} ai={r.ai_only} size="sm" />
                <EvidenceMeter level={r.evidence_level} label />
                {r.kano_class && <span className="chip">{KANO[r.kano_class]}</span>}
              </div>
              <div className="sl-markets">
                {r.markets.map((m) => (
                  <span key={m.market} className={`sl-mk${m.market === market ? " cur" : ""}`}>
                    <span>{m.label}</span>
                    <PriorityMark p={m.priority} ai={m.ai_only} size="sm" />
                  </span>
                ))}
              </div>
              <div className="row" style={{ gap: 8 }}>
                <Link className="btn btn-sm btn-primary" to={`/decide/req:${r.id}`}>
                  <Scale /> Decide
                </Link>
                <Link className="btn btn-sm" to={`/requirements/${r.id}?t=${encodeURIComponent(targetKey)}`}>
                  Full trace <ChevronRight />
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Equipment({ items, note }: { items: { name: string; availability: string }[]; note: string }) {
  return (
    <section className="sl-equip">
      <h2 className="sl-gh">Today's car in this area</h2>
      {items.length ? (
        <ul>
          {items.map((o) => (
            <li key={o.name}>
              <span>{o.name}</span>
              <span className="faint">{AVAIL[o.availability] ?? o.availability}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted t-small">Nothing on the current price list for this area.</p>
      )}
      <p className="faint t-micro">{note}</p>
    </section>
  );
}

function Comparison({ d }: { d: CarPayload }) {
  const nav = useNavigate();
  const markets = d.markets.map((m) => m.market);
  const rows = [...d.comparison].sort((a, b) => Number(b.differs) - Number(a.differs) || b.spread - a.spread);
  const differ = rows.filter((r) => r.differs).length;
  if (markets.length < 2) return null;
  return (
    <section className="panel cmp" aria-labelledby="cmp-h">
      <div className="panel-head">
        <h2 id="cmp-h">Same car, different customers</h2>
        <span className="t-small muted">
          {differ} of {rows.length} rank differently across markets
        </span>
      </div>
      <div className="cmp-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Requirement</th>
              {markets.map((m) => (
                <th key={m} className={m === d.market ? "cmp-cur" : undefined}>{MARKET[m] ?? m}</th>
              ))}
              <th className="r">Spread</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className={`clickable${r.differs ? " cmp-differs" : ""}`} onClick={() => nav(`/requirements/${r.id}`)}>
                <td>
                  <div className="ellipsis" style={{ maxWidth: 420 }}>{r.title}</div>
                </td>
                {markets.map((m) => {
                  const c = r.cells[m];
                  return (
                    <td key={m} className={m === d.market ? "cmp-cur" : undefined}>
                      {c ? (
                        <span className="row" style={{ gap: 8 }}>
                          <PriorityMark p={c.priority} ai={c.ai_only} size="sm" />
                          <span className="num faint t-small">{c.score == null ? "–" : Math.round(c.score)}</span>
                        </span>
                      ) : (
                        <span className="faint">—</span>
                      )}
                    </td>
                  );
                })}
                <td className="r num">{Math.round(r.spread)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MarketContext({ d }: { d: CarPayload }) {
  const p = d.market_profile;
  const mk = d.markets.find((m) => m.market === d.market);
  return (
    <section className="ctx">
      <div className="panel">
        <div className="panel-head">
          <h2>{p?.name ?? MARKET[d.market]} customers</h2>
          <Link className="t-small" to={`/markets/${d.market}`}>Market story <ChevronRight size={13} /></Link>
        </div>
        <div className="panel-body">
          {mk && mk.gaps.length > 0 && (
            <div className="ctx-gaps">
              {mk.gaps.map((g) => <span key={g} className="telltale amber">{g}</span>)}
            </div>
          )}
          <dl className="ctx-dl">
            {p?.climate && (<div><dt>Climate</dt><dd>{p.climate}</dd></div>)}
            {p?.usage_patterns && (<div><dt>How they drive</dt><dd>{p.usage_patterns}</dd></div>)}
            {p?.cultural_expectations && (<div><dt>What they expect</dt><dd>{p.cultural_expectations}</dd></div>)}
            {p?.infrastructure && (<div><dt>Charging & roads</dt><dd>{p.infrastructure}</dd></div>)}
          </dl>
        </div>
      </div>
      <div className="col" style={{ gap: 18 }}>
        <div className="panel">
          <div className="panel-head"><h2>Who it competes with</h2></div>
          <ul className="ctx-comp">
            {d.competitors.length === 0 && <li className="muted t-small">No competitor profiles for this car.</li>}
            {d.competitors.map((c) => (
              <li key={c.id}>
                <div className="ctx-comp-name">{c.name}</div>
                {c.strengths && <div className="muted t-small">{c.strengths}</div>}
              </li>
            ))}
          </ul>
        </div>
        <div className="panel panel-body ctx-build">
          <div className="sec-label">Where it's built</div>
          {d.production.map((p) => (
            <div key={p.plant + (p.market_variant ?? "")} className="t-small">
              <b>{p.plant}</b> <span className="muted">· {p.country}{p.market_variant ? ` · ${p.market_variant}` : ""}</span>
            </div>
          ))}
          {d.successor_launch && <div className="t-small muted" style={{ marginTop: 8 }}>Successor launch: {d.successor_launch}</div>}
          <p className="faint t-micro" style={{ marginTop: 8 }}>Plant and platform fit is a feasibility filter, never an engineering spec.</p>
        </div>
      </div>
    </section>
  );
}
