import Link from "next/link";

export default function Nav() {
  return (
    <nav className="border-b border-zinc-200 bg-white">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3 text-sm">
        <Link href="/" className="font-semibold text-zinc-900">ClaimLens</Link>
        <Link href="/intake" className="text-zinc-700 hover:text-sky-700">Intake</Link>
        <Link href="/dashboard" className="text-zinc-700 hover:text-sky-700">Dashboard</Link>
        <Link href="/analytics" className="text-zinc-700 hover:text-sky-700">Analytics</Link>
      </div>
    </nav>
  );
}
