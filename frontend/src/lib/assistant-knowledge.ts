// Local knowledge base for the floating Assistant (components/ai-assistant.tsx).
// Deliberately NOT a live LLM call - there is no chat/completion endpoint on
// the backend (see backend/app/api/routers/*), so faking one with a network
// request would either fail silently or lie about what the product does.
// Instead this is a transparent, keyword-matched FAQ over the platform's
// own real behavior (pricing rules, validation severities, normalization
// strategies, the optimization engines) - genuinely useful, and honest
// about being a documentation assistant rather than a general-purpose AI.

export interface KnowledgeEntry {
  id: string;
  keywords: string[];
  question: string;
  answer: string;
}

export const KNOWLEDGE_BASE: KnowledgeEntry[] = [
  {
    id: "pricing-discounts",
    keywords: ["discount", "sustained", "committed", "cud", "sud", "savings"],
    question: "How do discounts work?",
    answer:
      "On-demand compute automatically qualifies for Google's Sustained Use Discount as usage approaches a full month - no commitment needed. If you pick a 1-year or 3-year commitment term when creating an estimate, that's priced as a Committed Use Discount instead, which is deeper but locks you in. The Pricing page shows the exact discount percentages currently modeled.",
  },
  {
    id: "pricing-sources",
    keywords: ["price", "pricing", "cost", "sku", "how much", "rate"],
    question: "Where do prices come from?",
    answer:
      "Every dollar figure comes from a PricingProvider - either the built-in mock catalog or, when configured, the real Google Cloud Billing Catalog API. The AI/business logic never invents a number itself; it always asks the provider. You can see the exact source for each line item (SKU ID and provider name) in an estimate's cost breakdown.",
  },
  {
    id: "validation-severity",
    keywords: ["validation", "blocker", "warning", "severity", "invalid", "rule"],
    question: "What do validation severities mean?",
    answer:
      "Validation results come in three severities: info (a note worth knowing, doesn't block anything), warning (worth reviewing, but you can proceed), and blocker (the requested configuration isn't supported as-is). You can force an estimate through blockers if needed - the system will substitute the closest supported value and log it as an Assumption, transparently, rather than silently changing your input.",
  },
  {
    id: "normalization",
    keywords: ["normalization", "strategy", "conservative", "balanced", "performance", "assumption"],
    question: "What's normalization?",
    answer:
      "When your input is incomplete or ambiguous, the normalization engine fills the gap using one of three strategies: conservative (smallest reasonable sizing, cost-optimized), balanced (the default, aims for a realistic middle ground), or performance (headroom-first sizing for demanding workloads). Every substitution it makes is logged as an Assumption with a plain-English reason - nothing is changed silently.",
  },
  {
    id: "architecture",
    keywords: ["architecture", "recommend", "service", "design"],
    question: "How are architecture recommendations made?",
    answer:
      "The architecture recommendation engine maps your normalized requirement onto real GCP service layers (compute, storage, database, networking, and more) and explains the rationale for each choice - for example, recommending a regional load balancer once you've flagged high availability. It's derived logic over your requirement, not a generic template.",
  },
  {
    id: "optimization",
    keywords: ["optimi", "rightsiz", "forecast", "carbon", "budget", "commitment recommendation"],
    question: "What optimization features exist?",
    answer:
      "The platform's optimization engines cover rightsizing (flags over-provisioned resources from utilization data), Committed Use Discount recommendations, multi-month cost forecasting, a carbon footprint estimate, and region/cloud cost comparison - all reusing the same PricingProvider as every other estimate, never a separate ad-hoc calculation. Project budgets are tracked on the Projects pages.",
  },
  {
    id: "multi-cloud",
    keywords: ["aws", "azure", "multi-cloud", "multi cloud", "compare cloud"],
    question: "Does this support AWS or Azure?",
    answer:
      "Yes - alongside GCP, the platform has mock AWS and Azure catalog/pricing providers implementing the same interfaces, so a requirement can be priced against any of the three, or compared across all three at once. Live AWS/Azure pricing APIs aren't wired in yet; those providers currently use representative mock catalogs.",
  },
  {
    id: "export",
    keywords: ["export", "excel", "pdf", "report", "download"],
    question: "How do I export a report?",
    answer:
      "Open any saved estimate version and use the Export buttons, or go to Reports and pick a project/version - both generate a formatted Excel workbook or a client-ready PDF proposal on demand.",
  },
  {
    id: "excel-upload",
    keywords: ["upload", "template", "questionnaire", "xlsx", "spreadsheet"],
    question: "How does Excel intake work?",
    answer:
      "Download the blank questionnaire template from the Upload Excel page, fill it in offline, and upload it - the platform parses every field, flags anything it couldn't confidently read, and can generate an estimate immediately. The Questionnaire page offers the same intake as a guided step-by-step form instead, if you'd rather not use a spreadsheet.",
  },
];

export function answerAssistantQuery(query: string): { entry: KnowledgeEntry | null; text: string } {
  const q = query.toLowerCase();
  let best: KnowledgeEntry | null = null;
  let bestScore = 0;
  for (const entry of KNOWLEDGE_BASE) {
    const score = entry.keywords.filter((k) => q.includes(k)).length;
    if (score > bestScore) {
      bestScore = score;
      best = entry;
    }
  }
  if (best) return { entry: best, text: best.answer };
  return {
    entry: null,
    text:
      "I don't have a canned answer for that yet - try asking about pricing, discounts, validation severities, normalization strategies, architecture recommendations, or the optimization engines. You can also browse the Pricing, Validation, and Normalization pages directly.",
  };
}
