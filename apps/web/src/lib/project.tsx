"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { ErrorState, Spinner } from "@/components/ui/feedback";
import { useProjects } from "@/lib/queries";
import { readLocal, writeLocal } from "@/lib/storage";
import type { Project } from "@/lib/types";

export const PROJECT_KEY = "tokenprofiler-project";

type ProjectContext = {
  project: Project;
  projects: Project[];
  select: (id: string) => void;
};

const Context = createContext<ProjectContext | null>(null);

/**
 * Chooses the project every page works on. The remembered choice wins when it still
 * exists; otherwise the oldest project, so the default never depends on timing.
 */
export function pickProject(projects: Project[], remembered: string | null): Project | undefined {
  return projects.find((p) => p.id === remembered) ?? projects[0];
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const list = useProjects();
  const [chosen, setChosen] = useState<string | null>(() => readLocal(PROJECT_KEY));
  const select = useCallback((id: string) => {
    setChosen(id);
    writeLocal(PROJECT_KEY, id);
  }, []);
  const projects = list.data?.items;
  const project = projects ? pickProject(projects, chosen) : undefined;
  const value = useMemo(
    () => (project && projects ? { project, projects, select } : null),
    [project, projects, select],
  );

  if (list.error) {
    return <ErrorState className="h-full" message={list.error.message} onRetry={() => list.refetch()} />;
  }
  if (!value) {
    return (
      <div className="flex h-full min-h-64 items-center justify-center" role="status" aria-label="Loading">
        <Spinner className="size-5" />
      </div>
    );
  }
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useProject(): ProjectContext {
  const value = useContext(Context);
  if (!value) throw new Error("useProject must be used inside ProjectProvider");
  return value;
}
