// ⌘K: jump to any requirement, car · market, or screen from anywhere — the fastest path in a live demo.
import { useEffect } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { Command } from "cmdk";
import { useQuery } from "@tanstack/react-query";
import { Car, FileText, Globe2, Play, Presentation } from "lucide-react";
import { useStory } from "./Story";
import { api } from "@/lib/api";
import type { RequirementSummary } from "@/lib/types";
import { CAR, MARKET } from "@/lib/labels";
import { NAV } from "./Shell";

const CAR_MARKETS: [string, string[]][] = [
  ["F70", ["EU", "RoW"]],
  ["G60", ["US", "EU", "RoW"]],
  ["G68", ["CN"]],
  ["G70", ["US", "EU", "CN", "RoW"]],
];

export function CommandPalette({ open, setOpen }: { open: boolean; setOpen: (v: boolean) => void }) {
  const nav = useNavigate();
  const story = useStory();
  const reqs = useQuery({
    queryKey: ["requirements", "palette"],
    queryFn: () => api.get<RequirementSummary[]>("/api/requirements?include_rejected=true"),
    enabled: open,
  });

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!open);
      }
      if (e.key === "Escape" && open) setOpen(false);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, setOpen]);

  if (!open) return null;
  const go = (to: string) => {
    setOpen(false);
    nav(to);
  };
  return createPortal(
    <div className="cmdk-scrim" onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}>
      <Command className="cmdk-box" label="Search and commands" loop>
        <Command.Input autoFocus placeholder="Search requirements, cars, markets, screens…" />
        <Command.List>
          <Command.Empty>No match.</Command.Empty>
          <Command.Group heading="Go to">
            {NAV.map((n) => (
              <Command.Item key={n.to} value={`screen ${n.label}`} onSelect={() => go(n.to)}>
                <n.icon /> {n.label}
                <span className="cmdk-hint">{n.key}</span>
              </Command.Item>
            ))}
            <Command.Item value="start deciding queue review" onSelect={() => go("/decide")}>
              <Play /> Start deciding
            </Command.Item>
            <Command.Item value="present demo story pitch tour" onSelect={() => { setOpen(false); story.start(); }}>
              <Presentation /> Present the demo story
            </Command.Item>
          </Command.Group>
          <Command.Group heading="Cars">
            {CAR_MARKETS.flatMap(([v, ms]) =>
              ms.map((m) => (
                <Command.Item key={`${v}${m}`} value={`car ${CAR[v]} ${MARKET[m]} ${v} ${m}`} onSelect={() => go(`/cars/${v}?market=${m}`)}>
                  <Car /> {CAR[v]} · {MARKET[m]}
                </Command.Item>
              )),
            )}
          </Command.Group>
          <Command.Group heading="Markets">
            {Object.entries(MARKET).map(([m, l]) => (
              <Command.Item key={m} value={`market ${l} ${m}`} onSelect={() => go(`/markets/${m}`)}>
                <Globe2 /> {l}
              </Command.Item>
            ))}
          </Command.Group>
          <Command.Group heading="Requirements">
            {(reqs.data ?? []).map((r) => (
              <Command.Item key={r.id} value={`${r.id} ${r.title} ${r.category}`} onSelect={() => go(`/requirements/${r.id}`)}>
                <FileText />
                <span className="id">{r.id}</span>
                <span className="ellipsis">{r.title}</span>
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>
      </Command>
    </div>,
    document.body,
  );
}
