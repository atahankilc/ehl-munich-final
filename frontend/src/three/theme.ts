// Design tokens for the 3D stage — same values as the app's CSS (dark theme only).
export const THEME = {
  bg: "#08090b",
  panel: "#0e1014",
  hairline: "#1d2027",
  text: "#e8ebf0",
  muted: "#8a93a3",
  blue: "#1c69d4",
  blueBright: "#4d94ff",
  amber: "#f5a524",
  red: "#ff5a5f",
  green: "#3ccf91",
  font: '"Mona Sans Variable", "Mona Sans", system-ui, -apple-system, sans-serif',
} as const;

/** Length of every car in world units after normalisation. */
export const CAR_LENGTH = 4.8;
