"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import type { LanguageCode, PartyRole } from "@/lib/api";

const participants: Array<{ role: PartyRole; title: string; label: string }> = [
  { role: "hirer", title: "Participant 1", label: "Homeowner" },
  { role: "worker", title: "Participant 2", label: "Electrician" },
];

const languageNames: Record<LanguageCode, string> = {
  en: "English",
  hi: "Hindi",
};

export function DemoSetup() {
  const router = useRouter();
  const [languages, setLanguages] = useState<Record<PartyRole, LanguageCode>>({
    hirer: "en",
    worker: "en",
  });
  const supported = languages.hirer === "en" && languages.worker === "en";

  const startDemo = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!supported) return;
    const query = new URLSearchParams({
      hirer_language: languages.hirer,
      worker_language: languages.worker,
    });
    router.push(`/demo?${query.toString()}`);
  };

  return (
    <main className="app-shell">
      <nav className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark">M</span>
          <span>MeaningSync</span>
        </Link>
      </nav>
      <section className="setup-page">
        <header className="flow-heading">
          <span>Demo setup</span>
          <h1>Choose the conversation languages</h1>
          <p>Each person can use the language they are most comfortable with.</p>
        </header>

        <form onSubmit={startDemo}>
          <div className="setup-grid">
            {participants.map((participant) => (
              <article className="setup-card" key={participant.role}>
                <div className="setup-participant">
                  <span>{participant.title}</span>
                  <h2>{participant.label}</h2>
                </div>
                <label htmlFor={`${participant.role}-language`}>Language</label>
                <select
                  id={`${participant.role}-language`}
                  value={languages[participant.role]}
                  onChange={(event) =>
                    setLanguages((current) => ({
                      ...current,
                      [participant.role]: event.target.value as LanguageCode,
                    }))
                  }
                >
                  <option value="en">English</option>
                  <option value="hi" disabled>
                    Hindi — Coming soon
                  </option>
                </select>
              </article>
            ))}
          </div>

          <div className="setup-status" role="status">
            <span>Selected conversation</span>
            <strong>
              {languageNames[languages.hirer]} ↔ {languageNames[languages.worker]}
            </strong>
          </div>
          <p className="setup-availability">
            English conversations are available now. Hindi and mixed-language
            conversations are coming next.
          </p>

          <div className="setup-actions">
            <Link className="button secondary" href="/">
              Back to home
            </Link>
            <button className="button primary" type="submit" disabled={!supported}>
              Start Demo <span>→</span>
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
