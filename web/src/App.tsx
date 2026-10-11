import { lazy, Suspense, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { Band, Dock } from "@/components/Shell";
import { CommandPalette } from "@/components/CommandPalette";
import { StoryCard } from "@/components/Story";
import { SkeletonBlock } from "@/components/ui";

const Briefing = lazy(() => import("@/screens/Briefing"));
const Decide = lazy(() => import("@/screens/Decide"));
const Cars = lazy(() => import("@/screens/Cars"));
const Markets = lazy(() => import("@/screens/Markets"));
const Requirement = lazy(() => import("@/screens/Requirement"));
const Evidence = lazy(() => import("@/screens/Evidence"));
const Process = lazy(() => import("@/screens/Process"));
const NotFound = lazy(() => import("@/screens/NotFound"));

function Loading() {
  return (
    <div className="page">
      <SkeletonBlock lines={6} />
    </div>
  );
}

export default function App() {
  const [palette, setPalette] = useState(false);
  return (
    <>
      <Band onOpenPalette={() => setPalette(true)} />
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Briefing />} />
          <Route path="/decide" element={<Decide />} />
          <Route path="/decide/:uid" element={<Decide />} />
          <Route path="/cars" element={<Cars />} />
          <Route path="/cars/:vehicle" element={<Cars />} />
          <Route path="/markets" element={<Markets />} />
          <Route path="/markets/:market" element={<Markets />} />
          <Route path="/requirements/:id" element={<Requirement />} />
          <Route path="/evidence" element={<Evidence />} />
          <Route path="/process" element={<Process />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
      <Dock onOpenPalette={() => setPalette(true)} />
      <CommandPalette open={palette} setOpen={setPalette} />
      <StoryCard />
    </>
  );
}
