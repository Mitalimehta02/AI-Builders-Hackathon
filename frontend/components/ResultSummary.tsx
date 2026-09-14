import type { CaseDetail } from "@/lib/api";

const tierStyle = {
  HIGH: "bg-emerald-100 text-emerald-800",
  MEDIUM: "bg-amber-100 text-amber-800",
  LOW: "bg-rose-100 text-rose-800",
};

type Props = Pick<CaseDetail, "decision" | "confidence_tier" | "gate" | "cap_applied" | "orderings_agree">;

// Recommendation, confidence tier and what happens next, as three labelled badges.
export default function ResultSummary({ decision, confidence_tier, gate, cap_applied, orderings_agree }: Props) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3">
        <Badge label="Recommendation" value={decision ?? "—"}
          className={decision === "DENY" ? "bg-rose-100 text-rose-800" : "bg-sky-100 text-sky-800"} />
        <Badge label="Confidence" value={confidence_tier ?? "—"}
          className={confidence_tier ? tierStyle[confidence_tier] : "bg-zinc-100 text-zinc-700"} />
        <Badge label="Outcome" value={gate === "auto_resolved" ? "Auto-resolved" : gate === "human_review" ? "Sent to human review" : "—"}
          className={gate === "auto_resolved" ? "bg-emerald-100 text-emerald-800" : "bg-zinc-100 text-zinc-800"} />
      </div>
      {orderings_agree === false && (
        <p className="text-sm text-zinc-600">The judge reached different decisions when the arguments were presented in the opposite order, so confidence is LOW.</p>
      )}
      {cap_applied && (
        <p className="text-sm text-zinc-600">Confidence was lowered from HIGH because a significant point against the decision was not answered with a case-file fact.</p>
      )}
    </div>
  );
}

function Badge({ label, value, className }: { label: string; value: string; className: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</span>
      <span className={`rounded-md px-3 py-1 text-sm font-semibold ${className}`}>{value}</span>
    </div>
  );
}
