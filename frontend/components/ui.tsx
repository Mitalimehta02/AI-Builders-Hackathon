// Shared building blocks so every page looks and behaves the same: page layout, cards, buttons,
// and the loading, error and empty states.

import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

export const buttonStyles = {
  primary:
    "inline-flex min-h-11 items-center justify-center rounded-md bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-700",
  secondary:
    "inline-flex min-h-11 items-center justify-center rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold text-zinc-800 hover:border-zinc-500",
};

export function Page({ children }: { children: ReactNode }) {
  return <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">{children}</main>;
}

export function PageHeader({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <header className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold text-zinc-900">{title}</h1>
      {description && <p className="text-sm text-zinc-600">{description}</p>}
    </header>
  );
}

export function Card({ title, subtitle, children, className = "" }: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 sm:p-5 ${className}`}>
      {title && (
        <div>
          <h2 className="text-base font-semibold text-zinc-900 sm:text-lg">{title}</h2>
          {subtitle && <p className="text-sm text-zinc-600">{subtitle}</p>}
        </div>
      )}
      {children}
    </section>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white p-4 text-sm text-zinc-700">
      <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-sky-700" />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry, title }: { error: Error; onRetry?: () => void; title?: string }) {
  const unreachable = error instanceof ApiError && error.unreachable;
  return (
    <div role="alert" className="flex flex-col gap-2 rounded-lg border border-rose-300 bg-rose-50 p-4 text-sm text-rose-900">
      <p className="font-semibold">{title ?? (unreachable ? "Can't reach the ClaimLens backend" : "Something went wrong")}</p>
      <p>
        {unreachable
          ? "The API server isn't responding. On the hosted demo the server sleeps when idle and can take up to a minute to wake up."
          : error.message}
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry} className={`${buttonStyles.secondary} self-start`}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-dashed border-zinc-300 bg-white p-6 text-center">
      <p className="text-sm font-semibold text-zinc-800">{title}</p>
      {children && <p className="text-sm text-zinc-600">{children}</p>}
    </div>
  );
}
