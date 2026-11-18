import { Suspense } from "react";

import { TraceDetailView } from "@/components/traces/trace-detail";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <TraceDetailView id={id} />
    </Suspense>
  );
}
