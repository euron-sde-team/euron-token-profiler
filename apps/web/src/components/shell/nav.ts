import {
  Bell,
  Bot,
  Cpu,
  KeyRound,
  LayoutDashboard,
  ListTree,
  ScrollText,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  /** The path under the app root. */
  href: string;
  label: string;
  icon: LucideIcon;
};

export type NavGroup = { label: string | null; items: NavItem[] };

/** The sidebar, in the order of the dashboard route map. */
export const NAV_GROUPS: NavGroup[] = [
  { label: null, items: [{ href: "/overview", label: "Overview", icon: LayoutDashboard }] },
  {
    label: "Observe",
    items: [
      { href: "/traces", label: "Traces", icon: ListTree },
      { href: "/prompts", label: "Prompts", icon: ScrollText },
    ],
  },
  {
    label: "Attribute",
    items: [
      { href: "/models", label: "Models", icon: Cpu },
      { href: "/agents", label: "Agents and tools", icon: Bot },
    ],
  },
  {
    label: "Control",
    items: [
      { href: "/budgets", label: "Budgets and alerts", icon: Bell },
      { href: "/keys", label: "API keys", icon: KeyRound },
    ],
  },
  { label: null, items: [{ href: "/settings", label: "Settings", icon: Settings }] },
];

/** Whether a nav item covers the current path (detail pages keep their section highlighted). */
export function isNavActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
