import { describe, expect, it } from "vitest";

import { pickProject } from "@/lib/project";
import type { Project } from "@/lib/types";

const project = (id: string) => ({ id }) as Project;

describe("pickProject", () => {
  const projects = [project("a"), project("b")];

  it("honours a remembered project that still exists", () => {
    expect(pickProject(projects, "b")?.id).toBe("b");
  });

  it("falls back to the oldest project", () => {
    expect(pickProject(projects, "gone")?.id).toBe("a");
    expect(pickProject(projects, null)?.id).toBe("a");
  });

  it("returns nothing for no projects", () => {
    expect(pickProject([], "a")).toBeUndefined();
  });
});
