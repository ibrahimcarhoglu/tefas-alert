"use client";

import GlossaryTooltip from "./GlossaryTooltip";
import { getGlossaryDefinition } from "@/lib/glossary";

interface GlossaryTermProps {
  term: string;
  definition?: string;
  children?: React.ReactNode;
}

/** Sözlükten tanımı otomatik çeker; yoksa verilen definition kullanılır. */
export default function GlossaryTerm({ term, definition, children }: GlossaryTermProps) {
  const def = definition ?? getGlossaryDefinition(term);
  if (!def) {
    return <>{children ?? term}</>;
  }
  return (
    <GlossaryTooltip term={term} definition={def}>
      {children}
    </GlossaryTooltip>
  );
}
