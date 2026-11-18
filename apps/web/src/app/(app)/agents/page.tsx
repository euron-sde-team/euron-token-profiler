import { Suspense } from "react";

import { AgentsView } from "@/components/attribution/agents-view";

export default function Page() {
  return (
    <Suspense>
      <AgentsView />
    </Suspense>
  );
}
