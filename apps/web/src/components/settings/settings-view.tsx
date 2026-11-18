"use client";

import { AccountPanel } from "@/components/settings/account-panel";
import { ActivityPanel } from "@/components/settings/activity-panel";
import { ArchivesPanel } from "@/components/settings/archives-panel";
import { PeoplePanel } from "@/components/settings/people-panel";
import { ProjectPanel } from "@/components/settings/project-panel";
import { PageBody, PageHeader } from "@/components/ui/page";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCan } from "@/lib/queries";
import { useUrlParams } from "@/lib/use-url-params";

export function SettingsView() {
  const admin = useCan("admin");
  const { get, update } = useUrlParams();
  const requested = get("tab") ?? "project";
  const tab = !admin && ["people", "activity", "archives"].includes(requested) ? "project" : requested;
  return (
    <PageBody className="max-w-5xl">
      <PageHeader
        title="Settings"
        description="How this project ingests, protects and keeps data, who can sign in, and your account."
      />
      <Tabs value={tab} onValueChange={(value) => update({ tab: value === "project" ? null : value })}>
        <TabsList>
          <TabsTrigger value="project">Project</TabsTrigger>
          {admin ? <TabsTrigger value="people">People</TabsTrigger> : null}
          {admin ? <TabsTrigger value="activity">Activity</TabsTrigger> : null}
          {admin ? <TabsTrigger value="archives">Archives</TabsTrigger> : null}
          <TabsTrigger value="account">Account</TabsTrigger>
        </TabsList>
        <TabsContent value="project">
          <ProjectPanel />
        </TabsContent>
        {admin ? (
          <TabsContent value="people">
            <PeoplePanel />
          </TabsContent>
        ) : null}
        {admin ? (
          <TabsContent value="activity">
            <ActivityPanel />
          </TabsContent>
        ) : null}
        {admin ? (
          <TabsContent value="archives">
            <ArchivesPanel />
          </TabsContent>
        ) : null}
        <TabsContent value="account">
          <AccountPanel />
        </TabsContent>
      </Tabs>
    </PageBody>
  );
}
