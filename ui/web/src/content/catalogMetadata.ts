export type CategoryDescription = {
  title: string;
  whatIsIt: string;
  whatIsItFor: string;
};

type CatalogPayloadLike = Record<string, unknown> | null | undefined;

export const CATEGORY_DESCRIPTIONS: Record<string, CategoryDescription> = {
  decision_policies: {
    title: "Decision Policies",
    whatIsIt: "Runtime policies, plus declarative examples that describe policy composition.",
    whatIsItFor: "They define how the system turns market context into trading actions, while assets show how future policy composition could look."
  },
  policy_engines: {
    title: "Policy Engines",
    whatIsIt: "Code engines that build runtime decision policies.",
    whatIsItFor: "They keep policy behavior in code while declarative policies stay lightweight. In the current system they are mainly compatibility seams."
  },
  genome_schemas: {
    title: "Genome Schemas",
    whatIsIt: "Structural definitions of how a valid genome is composed.",
    whatIsItFor: "They define which modules exist and how genes fit together."
  },
  gene_type_definitions: {
    title: "Gene Type Definitions",
    whatIsIt: "Descriptive metadata for gene blocks and their fields.",
    whatIsItFor: "They help explain which parameters exist and how a future UI could present them."
  },
  signal_packs: {
    title: "Signal Packs",
    whatIsIt: "Runtime signal bundles, plus declarative examples of signal composition.",
    whatIsItFor: "They describe the signal inputs available to policy logic and experiments."
  },
  signal_plugins: {
    title: "Signal Plugins",
    whatIsIt: "Code-side extension points for signal-related behavior.",
    whatIsItFor: "They would allow the system to add signal implementations without changing the protected core. This category is currently future-facing and may be empty."
  },
  mutation_profiles: {
    title: "Mutation Profiles",
    whatIsIt: "Named mutation settings that shape how genomes are perturbed.",
    whatIsItFor: "They control search behavior without changing the meaning of the strategy."
  },
  experiment_presets: {
    title: "Experiment Presets",
    whatIsIt: "A mixed category of runtime execution presets and declarative experiment examples.",
    whatIsItFor: "Runtime presets shape generation and seed budgets, while asset presets bundle together reusable experiment compositions."
  }
};

export function getCategoryDescription(category: string): CategoryDescription {
  return (
    CATEGORY_DESCRIPTIONS[category] ?? {
      title: formatHumanLabel(category),
      whatIsIt: "A catalog category exposed by the experimental system.",
      whatIsItFor: "It groups related metadata so the system is easier to inspect."
    }
  );
}

export function formatHumanLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\bv(\d+)\b/gi, "v$1")
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getStringField(payload: CatalogPayloadLike, field: string): string | null {
  const value = payload?.[field];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function getDisplayLabel(id: string, payload?: CatalogPayloadLike): string {
  const metadataLabel =
    getStringField(payload, "label") ??
    getStringField(payload, "title") ??
    getStringField(payload, "name");

  if (metadataLabel && metadataLabel !== id) {
    return formatHumanLabel(metadataLabel);
  }

  return formatHumanLabel(id);
}

export function describeOrigin(origin: "runtime" | "asset" | "plugin"): string {
  if (origin === "runtime") {
    return "Provided by active runtime code";
  }
  if (origin === "asset") {
    return "Loaded from declarative asset file";
  }
  return "Provided by plugin-style code";
}
