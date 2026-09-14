import type { CaseDetail, JudgeRuling, PointStatus } from "@/lib/api";
import { POINT_STATUS_LABEL, POINT_STATUS_STYLE } from "@/lib/labels";

// Every numbered point, how each judge ruling says the other side dealt with it, and whether it
// is one of the unresolved points that blocks a HIGH tier.
export default function PointAccounting({ detail }: { detail: CaseDetail }) {
  const transcript = detail.transcript;
  const first = transcript?.judge_prosecutor_first;
  const second = transcript?.judge_defender_first;
  if (!transcript?.prosecutor || !transcript.defender || !first?.point_assessments || !second?.point_assessments) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-zinc-900">Point-by-point accounting</h2>
        <p className="mt-1 text-sm text-zinc-600">Not recorded for this stored result (produced by an older protocol).</p>
      </section>
    );
  }

  const concededByDefender = new Set(
    transcript.defender.responses.filter((r) => r.position.startsWith("conced")).map((r) => r.responds_to),
  );
  const unresolved = new Set(
    [...(detail.unresolved_points?.prosecutor_first ?? []), ...(detail.unresolved_points?.defender_first ?? [])].map((p) => p.point_id),
  );
  const againstDecision = detail.decision === "APPROVE" ? "Prosecutor" : "Defender";
  const points = [
    ...transcript.prosecutor.points.map((point) => ({ ...point, side: "Prosecutor" })),
    ...transcript.defender.points.map((point) => ({ ...point, side: "Defender" })),
  ];

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Point-by-point accounting</h2>
        <p className="text-sm text-zinc-600">
          For every point, each judge ruling records how the other side dealt with it. With a recommendation of{" "}
          {detail.decision ?? "—"}, the {againstDecision.toLowerCase()}&apos;s points are the ones against the decision; highlighted
          rows are unresolved and block a HIGH tier.
        </p>
      </div>
      <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-2">Point</th>
              <th className="px-3 py-2">Judge, prosecutor first</th>
              <th className="px-3 py-2">Judge, defender first</th>
              <th className="px-3 py-2">Effect on confidence</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => {
              const blocks = unresolved.has(point.id);
              const isAgainst = point.side === againstDecision;
              return (
                <tr key={point.id} className={`border-t border-zinc-100 align-top ${blocks ? "bg-rose-50" : ""}`}>
                  <td className="px-3 py-3">
                    <div className="flex gap-2">
                      <span className={`h-fit rounded px-2 py-0.5 text-xs font-bold ${point.side === "Prosecutor" ? "bg-rose-100 text-rose-800" : "bg-sky-100 text-sky-800"}`}>
                        {point.id}
                      </span>
                      <span className="text-zinc-800">{point.point}</span>
                    </div>
                    {concededByDefender.has(point.id) && (
                      <span className="mt-1 inline-block rounded bg-rose-600 px-2 py-0.5 text-xs font-semibold text-white">Defender conceded this point</span>
                    )}
                  </td>
                  <td className="px-3 py-3"><AssessmentCell ruling={first} pointId={point.id} /></td>
                  <td className="px-3 py-3"><AssessmentCell ruling={second} pointId={point.id} /></td>
                  <td className="px-3 py-3 text-xs">
                    {blocks ? (
                      <span className="font-semibold text-rose-700">Unresolved — blocks HIGH</span>
                    ) : isAgainst ? (
                      <span className="text-zinc-600">Against the decision, resolved</span>
                    ) : (
                      <span className="text-zinc-500">Supports the decision</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AssessmentCell({ ruling, pointId }: { ruling: JudgeRuling; pointId: string }) {
  const assessment = ruling.point_assessments?.find((a) => a.point_id === pointId);
  const status: PointStatus = assessment?.status ?? "not_assessed";
  return (
    <div className="flex flex-col gap-1">
      <span className={`w-fit rounded px-2 py-0.5 text-xs font-semibold ${POINT_STATUS_STYLE[status]}`}>{POINT_STATUS_LABEL[status]}</span>
      {assessment && <span className="text-xs text-zinc-500">{assessment.significant ? "significant" : "not significant"}</span>}
    </div>
  );
}
