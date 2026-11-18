import { Suspense } from "react";

import { PromptsView } from "@/components/prompts/prompts-view";

export default function Page() {
  return (
    <Suspense>
      <PromptsView />
    </Suspense>
  );
}
