import type { Tier } from "@/lib/api";

const LEVELS: { tier: Tier; meaning: string; active: string }[] = [
  { tier: "LOW", meaning: "judges disagree, or both unsure", active: "bg-rose-600 text-white" },
  { tier: "MEDIUM", meaning: "judges agree, not both certain", active: "bg-amber-500 text-white" },
  { tier: "HIGH", meaning: "both judges agree and are certain", active: "bg-emerald-600 text-white" },
];

// Three-step gauge. If the cap lowered the tier, the tier before the cap is shown as a dashed outline.
export default function ConfidenceGauge({ tier, tierBeforeCap }: { tier: Tier | null; tierBeforeCap?: Tier | null }) {
  const capped = Boolean(tier && tierBeforeCap && tierBeforeCap !== tier);
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-3 gap-1" role="img" aria-label={`Confidence tier ${tier ?? "unknown"}`}>
        {LEVELS.map((level) => {
          const isFinal = level.tier === tier;
          const isBeforeCap = capped && level.tier === tierBeforeCap;
          return (
            <div key={level.tier} className={`flex flex-col items-center rounded-md px-2 py-3 text-center ${
              isFinal ? level.active : isBeforeCap ? "border-2 border-dashed border-zinc-500 bg-white text-zinc-600" : "bg-zinc-100 text-zinc-400"
            }`}>
              <span className="text-sm font-bold">{level.tier}</span>
              <span className="text-[11px] leading-tight">{isBeforeCap ? "before the cap" : level.meaning}</span>
            </div>
          );
        })}
      </div>
      {capped && (
        <p className="text-sm font-semibold text-rose-700">Capped by the point accounting: {tierBeforeCap} → {tier}</p>
      )}
    </div>
  );
}
