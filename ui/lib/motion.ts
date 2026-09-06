// Every duration and easing lives here. Motion that does not carry information
// — order, causality, rejection — does not ship, and nothing loops forever:
// an infinite animation reads as a loading state.
export const motionTokens = {
  instant: 0.12,
  fast: 0.2,
  base: 0.32,
  slow: 0.5,
  ease: [0.22, 1, 0.36, 1] as const,
  spring: { type: "spring" as const, stiffness: 380, damping: 32 },
  stagger: 0.024,
};
