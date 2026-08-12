export const SCOPE_EXPLANATIONS: Record<string, string> = {
  org_wide_only: "Target metrics are only defined at the organization level.",
  unavailable_for_category: "Growth & forecast metrics require full time-series data which is unavailable at the single category scope.",
  category_restricted: "This view is scoped exclusively to your assigned category.",
};

export function getScopeExplanation(scopeFlagKey: string | null | undefined): string {
  if (!scopeFlagKey) return "Not available at category level";
  return SCOPE_EXPLANATIONS[scopeFlagKey] || "Not available at category level";
}
