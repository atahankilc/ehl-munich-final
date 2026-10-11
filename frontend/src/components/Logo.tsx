// SharkSight mark: a great white's head from the side, abstracted to one geometric line (dome, snout, mouth, jaw).
// D-044.
export function LogoMark({ height = 27 }: { height?: number }) {
  return (
    <svg width={height * 1.25} height={height} viewBox="0 0 100 80" fill="none" aria-hidden className="logo-mark">
      <path d="M6 18C40 18 72 26 94 46L36 52L66 60L10 72" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
