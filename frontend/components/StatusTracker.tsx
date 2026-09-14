import type { ClaimStatus, StatusResponse } from "@/lib/api";

const STEPS: { status: ClaimStatus; label: string }[] = [
  { status: "pending", label: "Queued" },
  { status: "gathering_evidence", label: "Gathering evidence" },
  { status: "debating", label: "Prosecutor and defender argue; judge rules" },
  { status: "calibrating", label: "Judge re-checks with the arguments swapped" },
  { status: "resolved", label: "Resolved" },
];

// Live progress for a submitted claim, driven by GET /claims/{id}/status.
export default function StatusTracker({ status }: { status: StatusResponse | null }) {
  const current = status ? STEPS.findIndex((step) => step.status === status.status) : 0;
  const failed = status?.status === "failed";

  return (
    <div className="flex flex-col gap-3" aria-live="polite">
      <ol className="flex flex-col gap-2">
        {STEPS.map((step, index) => {
          const done = !failed && (index < current || status?.status === "resolved");
          const active = !failed && index === current && status?.status !== "resolved";
          return (
            <li key={step.status} className="flex items-center gap-3 text-sm">
              <span aria-hidden="true" className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                done ? "bg-emerald-700 text-white" : active ? "animate-pulse bg-sky-700 text-white" : "bg-zinc-200 text-zinc-700"
              }`}>
                {done ? "✓" : index + 1}
              </span>
              <span className={done || active ? "font-medium text-zinc-900" : "text-zinc-600"}>
                {step.label}
                {done && <span className="sr-only"> (done)</span>}
                {active && <span className="ml-1 text-xs font-normal text-sky-800">in progress…</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {status && status.steps_completed.length > 0 && (
        <p className="text-xs text-zinc-600">Model steps completed: {status.steps_completed.join(", ")}</p>
      )}
      {failed && (
        <div role="alert" className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-900">
          <p className="font-semibold">Processing stopped before a decision was reached.</p>
          <p className="mt-1 [overflow-wrap:anywhere]">{status?.error}</p>
          <p className="mt-1">The debate steps listed above were saved with the claim. Submitting the claim again starts a new run.</p>
        </div>
      )}
    </div>
  );
}
