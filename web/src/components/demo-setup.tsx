"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { LiveProgress } from "@/components/live-flow-shell";
import type { CurrencyCode, LanguageCode, PartyRole } from "@/lib/api";

type DemoPreset = "english" | "bilingual";

export function DemoSetup() {
  const router = useRouter();
  const [preset, setPreset] = useState<DemoPreset>("english");
  const [currency, setCurrency] = useState<CurrencyCode>("INR");
  const languages: Record<PartyRole, LanguageCode> =
    preset === "bilingual"
      ? { hirer: "hi", worker: "en" }
      : { hirer: "en", worker: "en" };

  const startDemo = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = new URLSearchParams({
      hirer_language: languages.hirer,
      worker_language: languages.worker,
      currency,
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
        <LiveProgress
          currentStage="preferences"
          explanation="The Demo uses the same six-step flow with prepared data."
        />
        <header className="flow-heading">
          <span>Demo setup</span>
          <h1>Choose a prepared demo</h1>
          <p>Both presets are deterministic, key-free, and use the same six-step flow.</p>
        </header>

        <form onSubmit={startDemo}>
          <fieldset className="demo-preset-grid">
            <legend>Demo conversation</legend>
            <label>
              <input type="radio" name="demo-preset" value="english" checked={preset === "english"} onChange={() => setPreset("english")} />
              <span><strong>English Demo</strong><small>Homeowner and electrician both speak English.</small></span>
            </label>
            <label>
              <input type="radio" name="demo-preset" value="bilingual" checked={preset === "bilingual"} onChange={() => setPreset("bilingual")} />
              <span><strong>English / Hindi Demo</strong><small>Homeowner speaks Hindi; electrician speaks English.</small></span>
            </label>
          </fieldset>

          <div className="setup-status" role="status">
            <span>Selected conversation</span>
            <strong>
              {preset === "bilingual" ? "Hindi ↔ English" : "English ↔ English"}
            </strong>
          </div>
          <label className="setup-currency" htmlFor="demo-currency">
            Session currency
            <select
              id="demo-currency"
              value={currency}
              onChange={(event) =>
                setCurrency(event.target.value as CurrencyCode)
              }
            >
              <option value="INR">INR — Indian rupee</option>
              <option value="USD" disabled>USD — Available in Live Mode</option>
              <option value="EUR" disabled>EUR — Available in Live Mode</option>
            </select>
            <small>The prepared Demo uses INR evidence without conversion.</small>
          </label>
          <p className="setup-availability">No microphone or OpenAI request is used in Demo Mode.</p>

          <div className="setup-actions">
            <Link className="button secondary" href="/">
              Back to home
            </Link>
            <button className="button primary" type="submit">
              Start Demo <span>→</span>
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
