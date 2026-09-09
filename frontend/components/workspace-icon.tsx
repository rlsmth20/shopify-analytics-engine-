const paths: Record<string, string> = {
  DB: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  AQ: "m3 6 1 1 2-3 M9 6h12 M3 12h3 M9 12h12 M3 18h3 M9 18h12",
  FC: "M3 3v18h18 M6 15l5-5 4 3 6-8",
  IH: "m3 7 9-4 9 4-9 4Z M3 7v10l9 4 9-4V7 M12 11v10",
  RX: "M6 3h9l4 4v14H6z M14 3v5h5 M9 12h7 M9 16h7",
  SP: "M3 5h12v12H3z M15 10h4l3 4v3h-7 M8 18a2 2 0 1 1-4 0a2 2 0 1 1 4 0 M20 18a2 2 0 1 1-4 0a2 2 0 1 1 4 0",
  PO: "M3 4h2l3 11h10l3-8H6 M10 20h.01 M18 20h.01",
  TR: "M3 7h17l-4-4 M21 17H4l4 4",
  BO: "M8 3H3v5h5z M21 3h-5v5h5z M8 16H3v5h5z M21 16h-5v5h5z M8 5h8 M5 8v8 M19 8v8 M8 19h8",
  DS: "M3 7h18v14H3z M5 3h14v4 M9 12h6",
  SS: "M20 8a8 8 0 0 0-14-3L3 8 M3 3v5h5 M4 16a8 8 0 0 0 14 3l3-3 M16 16h5v5",
  IR: "M4 7h16 M4 17h16 M8 4v6 M16 14v6",
  AR: "M5 17h14l-2-4V8a5 5 0 0 0-10 0v5Z M10 21h4",
  AC: "M16 7a4 4 0 1 1-8 0 4 4 0 1 1 8 0 M4 21v-2a8 8 0 0 1 16 0v2",
  BL: "M3 5h18v14H3z M3 10h18 M6 15h4",
  PR: "m12 2 8 4v6q0 6-8 10-8-4-8-10V6Z m-4 10 3 3 5-6",
  CF: "M3 4h18v13H8l-5 4z M7 8h10 M7 12h6",
  SM: "M5 3h14v18H5z M8 8l2 2 5-5 M8 15h8",
  GR: "M3 21V3 M3 21h18 M7 17v-5 M12 17V8 M17 17V4",
  CSV: "M12 3v13 M7 8l5-5 5 5 M4 16v5h16v-5",
  menu: "M4 6h16 M4 12h16 M4 18h16",
};

export function WorkspaceIcon({ name }: { name: string }) {
  return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.DB} /></svg>;
}
