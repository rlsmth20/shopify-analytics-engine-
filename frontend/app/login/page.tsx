import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="login-shell">
      <section className="login-hero-panel">
        <div className="login-hero-copy">
          <p className="login-kicker">Inventory Command</p>
          <h1 className="login-title">
            Make the next inventory decision before it becomes expensive.
          </h1>
          <p className="login-copy">
            A prioritized action feed for operators who need to know what to
            reorder, what is overstocked, what is dead stock, and what to do
            first.
          </p>
        </div>

        <div className="login-value-grid">
          <div className="login-value-card">
            <span>Urgent stockout calls</span>
            <strong>Critical items rise to the top with profit at risk.</strong>
          </div>
          <div className="login-value-card">
            <span>Capital visibility</span>
            <strong>Overstock and dead stock stay tied to cash exposure.</strong>
          </div>
          <div className="login-value-card">
            <span>Operational trust</span>
            <strong>Sync status, lead times, and data quality stay visible.</strong>
          </div>
        </div>
      </section>

      <section className="login-card">
        <div className="login-card-header">
          <p className="section-eyebrow">Workspace Login</p>
          <h2 className="section-title">Enter your workspace</h2>
          <p className="section-copy">
            Authentication is not wired yet. This screen is a production-style
            shell for the next phase.
          </p>
        </div>

        <form className="stack-form">
          <label className="field-label">
            <span>Email</span>
            <input
              className="input-control"
              type="email"
              placeholder="operator@store.com"
            />
          </label>

          <label className="field-label">
            <span>Password</span>
            <input
              className="input-control"
              type="password"
              placeholder="Enter your password"
            />
          </label>

          <Link href="/dashboard" className="button button-primary button-full">
            Enter workspace
          </Link>
        </form>

        <p className="login-footnote">
          Current MVP access is manual. Shopify ingest, actions, and settings
          are available after entering the app shell.
        </p>
      </section>
    </main>
  );
}
