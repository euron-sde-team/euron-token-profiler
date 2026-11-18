"use client";

import { ErrorState } from "@/components/ui/feedback";

/** The last line of defence: a page that throws shows this instead of a blank screen. */
export default function RootError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <main>
      <ErrorState
        className="min-h-dvh"
        title="Something went wrong"
        message={error.message || "An unexpected error stopped this page from loading."}
        onRetry={reset}
      />
    </main>
  );
}
