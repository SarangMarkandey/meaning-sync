import type { LanguageCode, PartyRole } from "@/lib/api";
import { LiveSetup } from "@/components/live-setup";

/** Compatibility entry point for older imports; new sessions begin in setup. */
export function LiveExperience({
  participantLanguages,
}: {
  participantLanguages: Record<PartyRole, LanguageCode>;
}) {
  void participantLanguages;
  return <LiveSetup />;
}
