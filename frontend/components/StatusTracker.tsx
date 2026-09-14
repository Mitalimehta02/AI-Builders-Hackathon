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
    <div className="flex flex-col gap-3">
      <ol className="flex flex-col gap-2">
        {STEPS.map((step, index) => {
          const done = !failed && (index < current || status?.status === "resolved");
          const active = !failed && index === current && status?.status !== "resolved";
          return (
            <li key={step.status} className="flex items-center gap-3 text-sm">
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                done ? "bg-emerald-600 text-white" : active ? "bg-sky-600 text-white animate-pulse" : "bg-zinc-200 text-zinc-500"
              }`}>
                {done ? "✓" : index + 1}
              </span>
              <span className={done || active ? "font-medium text-zinc-900" : "text-zinc-500"}>{step.label}</span>
            </li>
          );
        })}
      </ol>
      {status && status.steps_completed.length > 0 && (
        <p className="text-xs text-zinc-500">Model steps completed: {status.steps_completed.join(", ")}</p>
      )}
      {failed && (
        <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">Processing failed: {status?.error}</p>
      )}
    </div>
  );
}
