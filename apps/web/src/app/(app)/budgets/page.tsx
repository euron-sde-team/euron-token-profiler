import { Suspense } from "react";

import { BudgetsView } from "@/components/budgets/budgets-view";

export default function Page() {
  return (
    <Suspense>
      <BudgetsView />
    </Suspense>
  );
}
