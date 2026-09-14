import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-6 px-6 py-16">
      <h1 className="text-3xl font-semibold text-zinc-900">ClaimLens</h1>
      <p className="text-lg text-zinc-700">
        An AI claims investigation copilot. A prosecutor and a defender argue each claim from the evidence, a judge rules
        twice with the arguments in opposite orders, and only confident, clean approvals resolve without a human.
      </p>
      <div className="flex flex-wrap gap-3">
        <Link href="/intake" className="rounded-md bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800">
          Submit or load a claim
        </Link>
      </div>
    </main>
  );
}
