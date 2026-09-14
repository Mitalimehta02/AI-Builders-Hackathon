import type { CaseDetail, PointStatus } from "@/lib/api";
import { POINT_STATUS_LABEL, POINT_STATUS_STYLE } from "@/lib/labels";

// The point-accounting cap, explained in plain language. This is the product's most distinctive
// safety step, so when it fires it is shown as a prominent card, not a footnote.
export default function CapExplanation({ detail }: { detail: CaseDetail }) {
  const unresolved = detail.unresolved_points;
  if (detail.cap_applied === undefined || detail.cap_applied === null || !unresolved) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-zinc-900">Confidence cap</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Not recorded for this stored result: it was produced before point-by-point accounting and the cap existed.
        </p>
      </section>
    );
  }

  const transcript = detail.transcript;
  const opposingSide = detail.decision === "APPROVE" ? "prosecutor" : "defender";
  const pointText = (id: string) =>
    [...(transcript?.prosecutor?.points ?? []), ...(transcript?.defender?.points ?? [])].find((p) => p.id === id)?.point ?? "";

  // Merge the two orderings' unresolved points into one row per point.
  const rows = new Map<string, { prosecutor_first?: PointStatus; defender_first?: PointStatus }>();
  for (const order of ["prosecutor_first", "defender_first"] as const) {
    for (const point of unresolved[order]) {
      rows.set(point.point_id, { ...rows.get(point.point_id), [order]: point.status });
    }
  }

  const rule = (
    <p className="mt-3 text-xs text-zinc-600">
      The rule is applied in code, not by the model: a HIGH tier becomes MEDIUM if any point against the decision was conceded,
      answered only by assertion, left unanswered while significant, or not assessed by the judge. The judge is not told the
      rule exists.
    </p>
  );

  if (detail.cap_applied) {
    return (
      <section className="rounded-lg border-2 border-rose-400 bg-rose-50 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-rose-700">Safety check fired</p>
        <h2 className="mt-1 text-xl font-semibold text-rose-900">Confidence cap applied: HIGH → MEDIUM</h2>
        <p className="mt-2 text-sm text-rose-900">
          Both judge rulings said HIGH, so this claim would otherwise have been{" "}
          {detail.decision === "APPROVE" ? "approved automatically without a human" : "recorded as a high-confidence denial"}.
          But these points from the {opposingSide} — the side arguing against the decision — were never answered with a fact from
          the case file:
        </p>
        <ul className="mt-3 flex flex-col gap-2">
          {[...rows.entries()].map(([id, statuses]) => (
            <li key={id} className="rounded-md bg-white p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-zinc-900 px-2 py-0.5 text-xs font-bold text-white">{id}</span>
                <span className="text-zinc-800">{pointText(id)}</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                {(["prosecutor_first", "defender_first"] as const).map((order) =>
                  statuses[order] ? (
                    <span key={order} className={`rounded px-2 py-0.5 ${POINT_STATUS_STYLE[statuses[order]!]}`}>
                      {order === "prosecutor_first" ? "Prosecutor-first judge" : "Defender-first judge"}: {POINT_STATUS_LABEL[statuses[order]!]}
                    </span>
                  ) : null,
                )}
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm font-semibold text-rose-900">
          So the tier was lowered to MEDIUM and the claim was sent to a human adjuster
          {detail.decision === "APPROVE" ? " instead of being auto-approved" : ""}.
        </p>
        {rule}
      </section>
    );
  }

  const notNeeded = detail.tier_before_cap !== "HIGH";
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-zinc-900">Confidence cap: did not fire</h2>
      <p className="mt-1 text-sm text-zinc-700">
        {notNeeded
          ? `It had nothing to lower: the two judge rulings did not both say HIGH (tier before the check: ${detail.tier_before_cap ?? "unknown"}).`
          : "Both judge rulings said HIGH, and every point against the decision was answered with a case-file fact or judged not significant."}
      </p>
      {notNeeded && rows.size > 0 && (
        <p className="mt-2 text-sm text-zinc-600">
          Points against the decision that would have capped a HIGH result: {[...rows.keys()].join(", ")}.
        </p>
      )}
      {rule}
    </section>
  );
}
