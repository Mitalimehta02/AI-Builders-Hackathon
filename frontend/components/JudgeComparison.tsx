import type { JudgeRuling } from "@/lib/api";
import { ORDERING_LABEL, TIER_STYLE } from "@/lib/labels";

// Both Judge rulings side by side: the same arguments, presented in opposite orders.
export default function JudgeComparison({ first, second }: { first?: JudgeRuling; second?: JudgeRuling }) {
  if (!first || !second) return null;
  const agree = first.decision === second.decision;
  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">The judge, ruling twice</h2>
        <p className="text-sm text-zinc-600">
          The same prosecutor and defender arguments were given to the judge twice, in opposite orders. A decision that changes
          when only the order changes is not one to act on.
        </p>
      </div>
      <div className={`rounded-md px-4 py-2 text-sm font-semibold ${agree ? "bg-emerald-50 text-emerald-900" : "bg-rose-50 text-rose-900"}`}>
        {agree
          ? `Both orderings reached the same decision: ${first.decision}`
          : `The orderings disagree (${first.decision} vs ${second.decision}), so confidence is LOW`}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Ruling label={ORDERING_LABEL.prosecutor_first} ruling={first} />
        <Ruling label={ORDERING_LABEL.defender_first} ruling={second} />
      </div>
    </section>
  );
}

function Ruling({ label, ruling }: { label: string; ruling: JudgeRuling }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-zinc-300 bg-white p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600">{label}</p>
      <div className="flex items-center gap-3">
        <span className={`text-lg font-bold ${ruling.decision === "DENY" ? "text-rose-700" : "text-sky-800"}`}>{ruling.decision}</span>
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${TIER_STYLE[ruling.verbalized_confidence]}`}>
          {ruling.verbalized_confidence} confidence
        </span>
      </div>
      <p className="text-sm text-zinc-800">{ruling.reasoning}</p>
      <p className="text-xs text-zinc-600">
        <span className="font-semibold">Why this confidence level:</span> {ruling.confidence_justification}
      </p>
    </div>
  );
}
