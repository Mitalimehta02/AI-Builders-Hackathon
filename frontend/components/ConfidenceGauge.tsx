import type { Tier } from "@/lib/api";

const LEVELS: { tier: Tier; meaning: string; active: string }[] = [
  { tier: "LOW", meaning: "judges disagree", active: "bg-rose-700 text-white" },
  { tier: "MEDIUM", meaning: "agree, not both certain", active: "bg-amber-200 text-amber-950" },
  { tier: "HIGH", meaning: "agree and both certain", active: "bg-emerald-700 text-white" },
];

// Three-step gauge. The final tier is marked in words as well as colour; if the cap lowered the
// tier, the tier before the cap is shown with a dashed outline.
export default function ConfidenceGauge({ tier, tierBeforeCap }: { tier: Tier | null; tierBeforeCap?: Tier | null }) {
  const capped = Boolean(tier && tierBeforeCap && tierBeforeCap !== tier);
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-3 gap-1" role="img" aria-label={`Confidence tier ${tier ?? "unknown"}${capped ? `, lowered from ${tierBeforeCap}` : ""}`}>
        {LEVELS.map((level) => {
          const isFinal = level.tier === tier;
          const isBeforeCap = capped && level.tier === tierBeforeCap;
          return (
            <div key={level.tier} className={`flex min-h-16 flex-col items-center justify-center rounded-md px-1 py-2 text-center ${
              isFinal ? `${level.active} ring-2 ring-zinc-900 ring-offset-1`
                : isBeforeCap ? "border-2 border-dashed border-zinc-600 bg-white text-zinc-700"
                : "bg-zinc-100 text-zinc-600"
            }`}>
              <span className="text-sm font-bold">{level.tier}</span>
              <span className="text-[11px] leading-tight">{isFinal ? "final tier" : isBeforeCap ? "before the cap" : level.meaning}</span>
            </div>
          );
        })}
      </div>
      {capped && <p className="text-sm font-semibold text-rose-700">Capped by the point accounting: {tierBeforeCap} → {tier}</p>}
    </div>
  );
}
