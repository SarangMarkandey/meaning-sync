"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import type { LanguageCode, PartyRole } from "@/lib/api";

const participants: Array<{ role: PartyRole; title: string; label: string }> = [
  { role: "hirer", title: "Participant 1", label: "Homeowner" },
  { role: "worker", title: "Participant 2", label: "Electrician" },
];

export function LiveSetup() {
  const router = useRouter();
  const [languages, setLanguages] = useState<Record<PartyRole, LanguageCode>>({
    hirer: "en",
    worker: "en",
  });
  const supported = languages.hirer === "en" && languages.worker === "en";

  const startLivePreview = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!supported) return;
    const query = new URLSearchParams({
      hirer_language: languages.hirer,
      worker_language: languages.worker,
    });
    router.push(`/live?${query.toString()}`);
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
          <span>Live analysis preview</span>
          <h1>Set up an English text conversation</h1>
          <p>
            Each person enters their own statements. MeaningSync analyzes the
            text after both participants have contributed.
          </p>
        </header>

        <div className="preview-notice" role="note">
          <strong>Text only in this milestone</strong>
          <span>No microphone, audio recording, or live transcription is used.</span>
        </div>

        <form onSubmit={startLivePreview}>
          <div className="setup-grid">
            {participants.map((participant) => (
              <article className="setup-card" key={participant.role}>
                <div className="setup-participant">
                  <span>{participant.title}</span>
                  <h2>{participant.label}</h2>
                </div>
                <label htmlFor={`live-${participant.role}-language`}>
                  Language
                </label>
                <select
                  id={`live-${participant.role}-language`}
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
            <strong>English ↔ English</strong>
          </div>
          <p className="setup-availability">
            English text analysis is available now. Hindi and mixed-language
            analysis remain planned.
          </p>

          <div className="setup-actions">
            <Link className="button secondary" href="/">
              Back to home
            </Link>
            <button className="button primary" type="submit" disabled={!supported}>
              Continue to conversation <span>→</span>
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
