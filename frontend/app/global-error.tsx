"use client";

export default function GlobalError() {
  return <html lang="en"><body style={{ fontFamily: "system-ui", padding: "3rem", maxWidth: "40rem", margin: "auto" }}>
    <h1>Skubase couldn’t open this page.</h1>
    <p>Reload to get the latest version. If the problem continues, contact info@skubase.io.</p>
    <button type="button" onClick={() => window.location.reload()}>Reload Skubase</button>
  </body></html>;
}
