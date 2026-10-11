// The two pages share one 3D volume: Evidence (raw sources) and Structure (what the AI made of them).
// Switching keeps the canvas mounted, so the comments fly into their clusters and back.
import { NavLink, useSearchParams } from "react-router-dom";
import { LogoMark } from "./Logo";
import "./pageswitch.css";

export function PageSwitch() {
  const [params] = useSearchParams();
  const q = params.toString() ? `?${params}` : "";
  return (
    <nav className="pageswitch" aria-label="Pages">
      <span className="brand"><LogoMark /><span className="brand-name">SharkSight</span></span>
      <NavLink to={`/${q}`} end>Evidence</NavLink>
      <NavLink to={`/structure${q}`}>Structure</NavLink>
      <NavLink to={`/definition${q}`}>Definition</NavLink>
      <NavLink to={`/prioritize${q}`}>Prioritize</NavLink>
      <NavLink to={`/document${q}`}>Document</NavLink>
    </nav>
  );
}
