/* Tiny client-side file-download helpers (no deps). Used by the export buttons. */
import type { Lead } from "@/types";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]) {
  if (rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [
    headers.join(","),
    ...rows.map((r) => headers.map((h) => escape(r[h])).join(",")),
  ].join("\n");
  triggerDownload(new Blob([csv], { type: "text/csv;charset=utf-8;" }), filename);
}

export function downloadText(filename: string, text: string) {
  triggerDownload(new Blob([text], { type: "text/plain;charset=utf-8;" }), filename);
}

/** Export an array of Leads as a flat CSV. */
export function exportLeadsCsv(leads: Lead[], filename = "leads.csv") {
  downloadCsv(
    filename,
    leads.map((l) => ({
      company: l.company,
      domain: l.domain,
      score: l.score,
      fit: l.fit,
      gov: l.gov,
      kind: l.kind,
      stage: l.stage,
      tags: l.tags.join(" | "),
      winProb: l.winProb ?? "",
    }))
  );
}
