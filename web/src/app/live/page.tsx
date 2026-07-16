import { redirect } from "next/navigation";

import { LiveExperience } from "@/components/live-experience";
import type { LanguageCode } from "@/lib/api";

type LiveSearchParams = {
  hirer_language?: string | string[];
  worker_language?: string | string[];
};

export default async function LivePage({
  searchParams,
}: {
  searchParams: Promise<LiveSearchParams>;
}) {
  const params = await searchParams;
  const hirerLanguage = params.hirer_language ?? "en";
  const workerLanguage = params.worker_language ?? "en";

  if (hirerLanguage !== "en" || workerLanguage !== "en") {
    redirect("/live/setup");
  }

  return (
    <LiveExperience
      participantLanguages={{
        hirer: hirerLanguage as LanguageCode,
        worker: workerLanguage as LanguageCode,
      }}
    />
  );
}
