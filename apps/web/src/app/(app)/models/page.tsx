import { Suspense } from "react";

import { ModelsView } from "@/components/attribution/models-view";

export default function Page() {
  return (
    <Suspense>
      <ModelsView />
    </Suspense>
  );
}
