import { Suspense } from "react";

import { OverviewView } from "@/components/overview/overview-view";

export default function Page() {
  return (
    <Suspense>
      <OverviewView />
    </Suspense>
  );
}
