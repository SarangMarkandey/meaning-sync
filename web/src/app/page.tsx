import Link from "next/link";

export default function Home() {
  return (
    <main className="app-shell">
      <nav className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark">M</span>
          <span>MeaningSync</span>
        </Link>
      </nav>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Clarity before commitment</p>
          <h1>Make sure both sides mean the same thing.</h1>
          <p className="hero-text">
            MeaningSync turns a spoken service agreement into a clear,
            evidence-linked view of what matches, what conflicts, and what was
            never discussed.
          </p>
          <div className="hero-actions">
            <Link className="button primary" href="/demo/setup">
              Try Demo <span>→</span>
            </Link>
            <Link className="button secondary" href="/live/setup">
              Start Live Session
              <small>English text preview</small>
            </Link>
          </div>
        </div>
        <div className="meaning-preview" aria-label="Agreement map preview">
          <div className="preview-top">
            <span>Shared meaning</span>
            <strong>4 of 9 clear</strong>
          </div>
          <div className="preview-ring">
            <span>44%</span>
          </div>
          <div className="preview-row good">
            <i />Scope &amp; price <b>Aligned</b>
          </div>
          <div className="preview-row warn">
            <i />Replacement parts <b>Different</b>
          </div>
          <div className="preview-row mute">
            <i />Payment timing <b>Not said</b>
          </div>
        </div>
      </section>
    </main>
  );
}
