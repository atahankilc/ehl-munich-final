// SharkSight: one scan volume per checkpoint. Screens are added as the pipeline stages are rebuilt
// (classify → cluster → contextualize → elicit); each reads the shared checkpoint from useCheckpoint().
import { Navigate, Route, Routes } from "react-router-dom";
import { CheckpointProvider } from "@/state/checkpoint";
import { SweepControl } from "@/components/SweepControl";
import { AuditPanel } from "@/components/AuditPanel";
import { Scan } from "@/screens/scan/Scan";

export default function App() {
  return (
    <CheckpointProvider>
      <Routes>
        <Route path="/" element={<Scan key="volume" />} />
        <Route path="/structure" element={<Scan key="volume" mode="structure" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <SweepControl />
      <AuditPanel />
    </CheckpointProvider>
  );
}
