import { Link } from "react-router-dom";
import { PageHead } from "@/components/Shell";

export default function NotFound() {
  return (
    <main className="page">
      <PageHead title="Nothing here" lede={<>This address doesn't match a screen. <Link to="/">Back to the briefing</Link>.</>} />
    </main>
  );
}
