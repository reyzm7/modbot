export const STEP_IDS = ["setup", "draw", "league", "qualification", "knockout", "champion"] as const;

export type StepId = (typeof STEP_IDS)[number];

export type StepDefinition = {
  id: StepId;
  label: string;
  short: string;
  href: string;
};

export const STEPS: StepDefinition[] = [
  { id: "setup", label: "Configuration", short: "Config", href: "/setup" },
  { id: "draw", label: "Tirage au sort", short: "Tirage", href: "/draw" },
  { id: "league", label: "Phase de ligue", short: "Ligue", href: "/league" },
  { id: "qualification", label: "Qualification", short: "Qualif", href: "/qualification" },
  { id: "knockout", label: "Phase finale", short: "Finale", href: "/knockout" },
  { id: "champion", label: "Sacre", short: "Sacre", href: "/champion" },
];

export function stepIndex(id: StepId): number {
  return STEPS.findIndex((step) => step.id === id);
}

export function stepBefore(id: StepId): StepDefinition | null {
  const index = stepIndex(id);
  return index > 0 ? STEPS[index - 1] : null;
}

export function stepAfter(id: StepId): StepDefinition | null {
  const index = stepIndex(id);
  return index >= 0 && index < STEPS.length - 1 ? STEPS[index + 1] : null;
}
