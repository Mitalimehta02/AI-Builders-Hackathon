import type { Point, Transcript } from "@/lib/api";

// The adversarial debate. Prosecutor and Defender are distinguished by more than colour: a labelled
// heading with a symbol (▲ / ●), a solid vs. dashed card border, and square vs. round point badges.
// The judge's rulings are shown separately (JudgeComparison).
export default function DebateTranscript({ transcript }: { transcript: Transcript }) {
  const { prosecutor, defender, prosecutor_rebuttal: rebuttal } = transcript;
  return (
    <section className="flex flex-col gap-3" aria-label="The debate">
      <h2 className="text-lg font-semibold text-zinc-900">The debate</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-3 rounded-lg border-2 border-solid border-rose-300 bg-white p-4 sm:p-5">
          <div>
            <p className="text-sm font-bold uppercase tracking-wide text-rose-800"><span aria-hidden="true">▲ </span>Prosecutor</p>
            <p className="text-sm text-zinc-600">Argues the claim should be denied</p>
          </div>
          {prosecutor?.points.map((point) => <PointItem key={point.id} point={point} side="prosecutor" />)}
          {prosecutor?.summary && <p className="border-t border-zinc-200 pt-2 text-sm italic text-zinc-700">{prosecutor.summary}</p>}
        </div>

        <div className="flex flex-col gap-3 rounded-lg border-2 border-dashed border-sky-400 bg-white p-4 sm:p-5">
          <div>
            <p className="text-sm font-bold uppercase tracking-wide text-sky-800"><span aria-hidden="true">● </span>Defender</p>
            <p className="text-sm text-zinc-600">Answers each prosecutor point, then argues the claim should be paid</p>
          </div>
          {defender?.responses.map((response, index) => {
            const conceded = response.position.startsWith("conced");
            return (
              <div key={`${response.responds_to}-${index}`} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-none bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-800">Reply to {response.responds_to}</span>
                  <span className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${conceded ? "bg-rose-100 text-rose-800" : "bg-sky-100 text-sky-800"}`}>
                    {conceded ? "concedes" : "rebuts"}
                  </span>
                </div>
                <p className="text-sm text-zinc-900">{response.response}</p>
                <p className="text-xs text-zinc-600 [overflow-wrap:anywhere]">Cites: {response.evidence}</p>
              </div>
            );
          })}
          {defender && defender.points.length > 0 && (
            <div className="flex flex-col gap-3 border-t border-zinc-200 pt-3">
              {defender.points.map((point) => <PointItem key={point.id} point={point} side="defender" />)}
            </div>
          )}
          {defender?.summary && <p className="border-t border-zinc-200 pt-2 text-sm italic text-zinc-700">{defender.summary}</p>}
        </div>
      </div>

      {rebuttal && (
        <div className="rounded-lg border border-dashed border-zinc-400 bg-zinc-50 p-4 sm:p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-700">
            Prosecutor rebuttal — older protocol (this round was removed before the final evaluation)
          </p>
          <div className="mt-2 flex flex-col gap-2">
            {rebuttal.rebuttals.length === 0 && <p className="text-sm text-zinc-700">No rebuttals.</p>}
            {rebuttal.rebuttals.map((item, index) => (
              <p key={index} className="text-sm text-zinc-800">
                <span className="mr-2 bg-zinc-200 px-2 py-0.5 text-xs font-semibold">Reply to {item.responds_to}</span>
                {item.rebuttal}
              </p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export function PointBadge({ id, side }: { id: string; side: "prosecutor" | "defender" }) {
  return side === "prosecutor" ? (
    <span className="h-fit shrink-0 rounded-none bg-rose-100 px-2 py-0.5 text-xs font-bold text-rose-800" title="Prosecutor point">▲ {id}</span>
  ) : (
    <span className="h-fit shrink-0 rounded-full bg-sky-100 px-2 py-0.5 text-xs font-bold text-sky-800" title="Defender point">● {id}</span>
  );
}

function PointItem({ point, side }: { point: Point; side: "prosecutor" | "defender" }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-2">
        <PointBadge id={point.id} side={side} />
        <p className="text-sm text-zinc-900">{point.point}</p>
      </div>
      <p className="text-xs text-zinc-600 [overflow-wrap:anywhere]">Cites: {point.evidence}</p>
    </div>
  );
}
