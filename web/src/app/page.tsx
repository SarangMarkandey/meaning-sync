import Link from "next/link";

export default function Home() {
  return (
    <main className="app-shell home-page">
      <nav className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark">M</span>
          <span>MeaningSync</span>
        </Link>
        <div className="home-nav" aria-label="Primary navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#trust">Trust &amp; privacy</a>
        </div>
      </nav>

      <section className="hero home-hero">
        <div className="hero-copy">
          <p className="eyebrow">Clarity before commitment</p>
          <h1>Make sure both sides mean the same thing.</h1>
          <p className="hero-text">
            MeaningSync compares a spoken or typed service agreement, identifies
            what matches, what differs and what remains open, then creates a
            clarity receipt confirmed by both people.
          </p>
          <div className="hero-actions">
            <Link className="button primary" href="/demo/setup">
              Try the demo <span>→</span>
            </Link>
            <Link className="button secondary" href="/live/setup">
              Start a live conversation
            </Link>
          </div>
          <p className="capability-line">English and Hindi · Text and audio · One device or separate devices</p>
        </div>

        <article className="agreement-preview" aria-label="Example agreement map">
          <header><span>Agreement preview</span><strong>Original evidence preserved</strong></header>
          <PreviewGroup title="What matches" tone="good" items={["Work starts today", "Labour price is ₹1,200"]} />
          <PreviewGroup title="Needs a decision" tone="warn" items={["Are replacement parts included?"]} />
          <PreviewGroup title="Not discussed" tone="mute" items={["Payment timing", "Warranty"]} />
        </article>
      </section>

      <section className="home-section how-section" id="how-it-works">
        <header><p className="eyebrow">How it works</p><h2>From conversation to shared clarity</h2></header>
        <div className="home-card-grid">
          <InfoCard number="01" title="Have the conversation">Speak or type naturally, together or from separate devices.</InfoCard>
          <InfoCard number="02" title="Check shared meaning">MeaningSync identifies matches, differences and open terms.</InfoCard>
          <InfoCard number="03" title="Confirm and receive a receipt">Both people confirm the same final understanding.</InfoCard>
        </div>
      </section>

      <section className="home-split">
        <article>
          <p className="eyebrow">Made for everyday work</p>
          <h2>A clearer handoff for both sides</h2>
          <p>For customers and service providers making everyday agreements—repairs, freelance work, home services and other informal jobs.</p>
        </article>
        <article>
          <p className="eyebrow">Bilingual by design</p>
          <h2>Use the language that feels natural</h2>
          <p>Each person can use English or Hindi. MeaningSync preserves the original words and shows the other participant a translated view when needed.</p>
        </article>
      </section>

      <section className="home-section trust-section" id="trust">
        <header><p className="eyebrow">Trust &amp; privacy</p><h2>Your words stay the evidence</h2></header>
        <ul>
          <li>Original words remain preserved.</li>
          <li>Translations never replace original evidence.</li>
          <li>MeaningSync does not store raw audio.</li>
          <li>Each participant confirms separately.</li>
          <li>Participant identity is not verified.</li>
          <li>A clarity receipt is not a legally enforceable contract.</li>
        </ul>
      </section>

      <section className="home-cta">
        <div><p className="eyebrow">See shared meaning clearly</p><h2>Try a prepared conversation in under three minutes.</h2></div>
        <Link className="button primary" href="/demo/setup">Try the demo <span>→</span></Link>
      </section>
    </main>
  );
}

function PreviewGroup({ title, tone, items }: { title: string; tone: string; items: string[] }) {
  return <section className={`preview-group ${tone}`}><h2>{title}</h2>{items.map((item) => <p key={item}><i aria-hidden="true" />{item}</p>)}</section>;
}

function InfoCard({ number, title, children }: { number: string; title: string; children: React.ReactNode }) {
  return <article className="home-info-card"><span>{number}</span><h3>{title}</h3><p>{children}</p></article>;
}
