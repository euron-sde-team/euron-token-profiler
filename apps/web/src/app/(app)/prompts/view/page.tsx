import { Suspense } from "react";

import { PromptDetailView } from "@/components/prompts/prompt-detail";

export default function Page() {
  return (
    <Suspense>
      <PromptDetailView />
    </Suspense>
  );
}
