import type { Transcript } from "@/lib/api";

// The adversarial debate: the prosecutor (for denial) and the defender (for payment) in separate,
// colour-coded columns. The judge's rulings are shown separately (JudgeComparison).
export default function DebateTranscript({ transcript }: { transcript: Transcript }) {
  const { prosecutor, defender, prosecutor_rebuttal: rebuttal } = transcript;
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold text-zinc-900">The debate</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 border-l-4 border-l-rose-500 bg-white p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-rose-700">Prosecutor</p>
            <p className="text-sm text-zinc-600">Argues the claim should be denied</p>
          </div>
          {prosecutor?.points.map((point) => (
            <div key={point.id} className="flex flex-col gap-1">
              <div className="flex gap-2">
                <span className="h-fit rounded bg-rose-100 px-2 py-0.5 text-xs font-bold text-rose-800">{point.id}</span>
                <p className="text-sm text-zinc-900">{point.point}</p>
              </div>
              <p className="pl-10 text-xs text-zinc-500">Cites: {point.evidence}</p>
            </div>
          ))}
          {prosecutor?.summary && <p className="border-t border-zinc-100 pt-2 text-sm italic text-zinc-700">{prosecutor.summary}</p>}
        </div>

        <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 border-l-4 border-l-sky-500 bg-white p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Defender</p>
            <p className="text-sm text-zinc-600">Answers each prosecutor point, then argues the claim should be paid</p>
          </div>
          {defender?.responses.map((response, index) => {
            const conceded = response.position.startsWith("conced");
            return (
              <div key={`${response.responds_to}-${index}`} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-700">re {response.responds_to}</span>
                  <span className={`rounded px-2 py-0.5 text-xs font-semibold ${conceded ? "bg-rose-100 text-rose-800" : "bg-sky-100 text-sky-800"}`}>
                    {conceded ? "concedes" : "rebuts"}
                  </span>
                </div>
                <p className="text-sm text-zinc-900">{response.response}</p>
                <p className="text-xs text-zinc-500">Cites: {response.evidence}</p>
              </div>
            );
          })}
          {defender && defender.points.length > 0 && (
            <div className="flex flex-col gap-2 border-t border-zinc-100 pt-2">
              {defender.points.map((point) => (
                <div key={point.id} className="flex flex-col gap-1">
                  <div className="flex gap-2">
                    <span className="h-fit rounded bg-sky-100 px-2 py-0.5 text-xs font-bold text-sky-800">{point.id}</span>
                    <p className="text-sm text-zinc-900">{point.point}</p>
                  </div>
                  <p className="pl-10 text-xs text-zinc-500">Cites: {point.evidence}</p>
                </div>
              ))}
            </div>
          )}
          {defender?.summary && <p className="border-t border-zinc-100 pt-2 text-sm italic text-zinc-700">{defender.summary}</p>}
        </div>
      </div>

      {rebuttal && (
        <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600">
            Prosecutor rebuttal — older protocol (this round was removed before the final evaluation)
          </p>
          <div className="mt-2 flex flex-col gap-2">
            {rebuttal.rebuttals.length === 0 && <p className="text-sm text-zinc-600">No rebuttals.</p>}
            {rebuttal.rebuttals.map((item, index) => (
              <p key={index} className="text-sm text-zinc-800">
                <span className="mr-2 rounded bg-zinc-200 px-2 py-0.5 text-xs font-semibold">re {item.responds_to}</span>
                {item.rebuttal}
              </p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
