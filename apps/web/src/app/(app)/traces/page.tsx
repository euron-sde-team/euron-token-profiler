import { Suspense } from "react";

import { TracesView } from "@/components/traces/traces-view";

export default function Page() {
  return (
    <Suspense>
      <TracesView />
    </Suspense>
  );
}
