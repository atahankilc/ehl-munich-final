// App chrome: the panoramic status band (top) and the floating dock (bottom). The band answers "where are we in
// the 2-year process, what's waiting, what has it cost" from any screen.
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { Archive, Car, Command, Gauge, Globe2, Inbox, Presentation, Search, Workflow } from "lucide-react";
import { useStory } from "./Story";
import { useAppState, useMeta } from "@/lib/hooks";
import { getActor, setActor } from "@/lib/api";
import { fmtSimDate, fmtUsd } from "@/lib/format";
import "./shell.css";

type NavItem = { to: string; label: string; icon: typeof Gauge; key: string; end?: boolean };
export const NAV: NavItem[] = [
  { to: "/", label: "Briefing", icon: Gauge, key: "1", end: true },
  { to: "/decide", label: "Decide", icon: Inbox, key: "2" },
  { to: "/cars", label: "Cars", icon: Car, key: "3" },
  { to: "/markets", label: "Markets", icon: Globe2, key: "4" },
  { to: "/evidence", label: "Evidence", icon: Archive, key: "5" },
  { to: "/process", label: "Process", icon: Workflow, key: "6" },
];

function Mark() {
  // Successor mark: an instrument arc with a forward tick — no third-party trademark.
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden className="mark">
      <path d="M4.2 16.5a8.5 8.5 0 1 1 15.6 0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M12 12.6 16.6 8" stroke="var(--blue-hi)" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="12" cy="12.6" r="1.7" fill="var(--blue-hi)" />
    </svg>
  );
}

function WaveStrip() {
  const { data: s } = useAppState();
  const { data: meta } = useMeta();
  const waves = meta ? Object.entries(meta.waves) : [];
  const cur = s?.current_wave ?? 0;
  return (
    <NavLink to="/process" className="wave-strip" title="The ~2-year requirements process, replayed as three evidence waves">
      <span className="sim">Simulation</span>
      <span className="wave-ticks" aria-hidden>
        {waves.map(([n]) => (
          <i key={n} className={Number(n) < cur ? "done" : Number(n) === cur ? "now" : ""} />
        ))}
      </span>
      {s?.running_job ? (
        <span className="telltale blue pulse">{s.running_job.kind === "wave" ? "Opening next wave…" : "AI is answering…"}</span>
      ) : s?.wave ? (
        <span className="wave-text">
          <b>Wave {cur}</b>
          <span className="muted"> · {s.wave.label.replace(/^Wave \d+ · /, "")} · {fmtSimDate(s.wave.simulated_date)}</span>
        </span>
      ) : (
        <span className="muted">No wave opened</span>
      )}
    </NavLink>
  );
}

function ActorChip() {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(getActor());
  const initials = name
    .replace(/\(.*\)/, "")
    .trim()
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  if (editing)
    return (
      <form
        className="actor-edit"
        onSubmit={(e) => {
          e.preventDefault();
          const v = name.trim() || "Atahan (PM)";
          setActor(v);
          setName(v);
          setEditing(false);
        }}
      >
        <input className="input" autoFocus value={name} onChange={(e) => setName(e.target.value)} onBlur={() => setEditing(false)} aria-label="Acting as" />
      </form>
    );
  return (
    <button className="actor" onClick={() => setEditing(true)} title="Acting as — the named person recorded on every decision. Click to change.">
      <span className="avatar">{initials || "PM"}</span>
      <span className="actor-name">{name}</span>
    </button>
  );
}

function Spend() {
  const { data: s } = useAppState();
  if (!s) return null;
  const pct = Math.min(100, (s.spend_usd / s.budget.total) * 100);
  return (
    <NavLink to="/process?tab=system" className="spend" title={`OpenAI spend ${fmtUsd(s.spend_usd)} of $${s.budget.total} — hard stop at $${s.budget.hard_stop}`}>
      <span className="spend-val num">{fmtUsd(s.spend_usd)}</span>
      <span className="spend-track">
        <span style={{ width: `${pct}%` }} />
        <i style={{ left: `${(s.budget.warn / s.budget.total) * 100}%` }} />
        <i style={{ left: `${(s.budget.hard_stop / s.budget.total) * 100}%` }} />
      </span>
    </NavLink>
  );
}

export function Band({ onOpenPalette }: { onOpenPalette: () => void }) {
  const { data: s } = useAppState();
  const waiting = s ? s.counts.to_review + s.counts.open_proposals - (s.counts.open_by_kind.new_requirement ?? 0) : 0;
  const story = useStory();
  return (
    <header className="band">
      <div className="band-left">
        <NavLink to="/" className="brand" aria-label="Successor — briefing">
          <Mark />
          <span className="brand-name">Successor</span>
        </NavLink>
        <span className="band-sep" />
        <WaveStrip />
      </div>
      <div className="band-right">
        {waiting > 0 && (
          <NavLink to="/decide" className="waiting" title="Requirements to review and AI suggestions waiting for your decision">
            <span className="waiting-n num">{waiting}</span> waiting for you
          </NavLink>
        )}
        <Spend />
        {!story.on && (
          <button className="btn btn-sm btn-ghost present-btn" onClick={story.start} title="Walk through the pitch, step by step, on the live app">
            <Presentation /> Present
          </button>
        )}
        <ActorChip />
        <button className="btn btn-sm palette-btn" onClick={onOpenPalette} aria-label="Search and commands">
          <Search />
          <span className="kbd">⌘K</span>
        </button>
      </div>
    </header>
  );
}

export function Dock({ onOpenPalette }: { onOpenPalette: () => void }) {
  const { data: s } = useAppState();
  const loc = useLocation();
  const nav = useNavigate();
  const waiting = s ? s.counts.to_review + s.counts.open_proposals - (s.counts.open_by_kind.new_requirement ?? 0) : 0;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const item = NAV.find((n) => n.key === e.key);
      if (item && !loc.pathname.startsWith("/decide")) {
        e.preventDefault();
        nav(item.to);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nav, loc.pathname]);

  return (
    <nav className="dock-wrap" aria-label="Main">
      <div className="dock">
        {NAV.map((n) => {
          const active = n.end ? loc.pathname === "/" : loc.pathname.startsWith(n.to);
          return (
            <NavLink key={n.to} to={n.to} end={n.end} className={`dock-item${active ? " active" : ""}`} title={`${n.label}  (${n.key})`}>
              {active && <motion.span layoutId="dock-active" className="dock-active" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
              <n.icon aria-hidden />
              <span className="dock-label">{n.label}</span>
              {n.to === "/decide" && waiting > 0 && <span className="dock-badge num">{waiting}</span>}
            </NavLink>
          );
        })}
      </div>
      <button className="dock-search" onClick={onOpenPalette} aria-label="Search and commands (⌘K)">
        <Command aria-hidden />
      </button>
    </nav>
  );
}

export function PageHead({ title, lede, actions }: { title: ReactNode; lede?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1 className="t-head">{title}</h1>
        {lede && <p className="lede">{lede}</p>}
      </div>
      {actions && <div className="row wrap">{actions}</div>}
    </div>
  );
}
