import { redirect } from "next/navigation";

import { DemoExperience } from "@/components/demo-experience";
import type { CurrencyCode, LanguageCode } from "@/lib/api";

type DemoSearchParams = {
  hirer_language?: string | string[];
  worker_language?: string | string[];
  currency?: string | string[];
};

export default async function DemoPage({
  searchParams,
}: {
  searchParams: Promise<DemoSearchParams>;
}) {
  const params = await searchParams;
  const hirerLanguage = params.hirer_language ?? "en";
  const workerLanguage = params.worker_language ?? "en";
  const currency = params.currency ?? "INR";

  if (
    !(
      (hirerLanguage === "en" && workerLanguage === "en") ||
      (hirerLanguage === "hi" && workerLanguage === "en")
    ) ||
    currency !== "INR"
  ) {
    redirect("/demo/setup");
  }

  return (
    <DemoExperience
      participantLanguages={{
        hirer: hirerLanguage as LanguageCode,
        worker: workerLanguage as LanguageCode,
      }}
      currency={currency as CurrencyCode}
    />
  );
}
