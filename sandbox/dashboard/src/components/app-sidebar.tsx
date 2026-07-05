"use client";

import { Activity, Boxes, CalendarClock, ChevronsUpDown, LayoutGrid, Network, Server, Settings, Terminal, Workflow } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { UserNav } from "./user-nav";

export type Section =
  | "overview"
  | "sessions"
  | "templates"
  | "schedule"
  | "fleet"
  | "architecture"
  | "settings";

const NAV: { id: Section; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "overview", label: "Overview", icon: LayoutGrid },
  { id: "sessions", label: "Sessions", icon: Activity },
  { id: "templates", label: "Templates", icon: Boxes },
  { id: "schedule", label: "Schedule", icon: CalendarClock },
  { id: "fleet", label: "Fleet", icon: Network },
  { id: "architecture", label: "How it works", icon: Workflow },
  { id: "settings", label: "Settings", icon: Settings },
];

export function AppSidebar({
  active,
  onSelect,
  counts,
}: {
  active: Section;
  onSelect: (s: Section) => void;
  counts: Partial<Record<Section, number>>;
}) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" className="data-[slot=sidebar-menu-button]:!p-1.5">
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Server className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">Flash</span>
                <span className="truncate text-xs text-muted-foreground">single-node</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4 opacity-50" />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Console</SidebarGroupLabel>
          <SidebarMenu>
            {NAV.map((item) => (
              <SidebarMenuItem key={item.id}>
                <SidebarMenuButton
                  isActive={active === item.id}
                  tooltip={item.label}
                  onClick={() => onSelect(item.id)}
                >
                  <item.icon />
                  <span>{item.label}</span>
                </SidebarMenuButton>
                {counts[item.id] != null && (
                  <SidebarMenuBadge>{counts[item.id]}</SidebarMenuBadge>
                )}
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Resources</SidebarGroupLabel>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton tooltip="Terminal" disabled>
                <Terminal />
                <span>Terminal</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="flex items-center gap-2 rounded-md p-1.5 group-data-[collapsible=icon]:p-0">
              <UserNav />
              <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                <span className="truncate font-medium">Demo User</span>
                <span className="truncate text-xs text-muted-foreground">demo@example.com</span>
              </div>
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
