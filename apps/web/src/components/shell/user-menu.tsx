"use client";

import { KeyRound, LogOut, Monitor, Moon, Sun, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PasswordDialog } from "@/components/shell/password-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { initials } from "@/lib/format";
import { useSignOut } from "@/lib/use-sign-out";
import { parseTheme, useTheme } from "@/lib/theme";
import type { User } from "@/lib/types";

export function UserMenu({ account }: { account: User }) {
  const { signOut } = useSignOut();
  const { preference, setTheme } = useTheme();
  const [changingPassword, setChangingPassword] = useState(false);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="hover:bg-muted flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors"
            aria-label={`Account menu for ${account.name}`}
          >
            <span className="bg-muted text-foreground ring-border flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ring-1">
              {initials(account.name)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] leading-tight font-medium">{account.name}</span>
              <span className="text-muted-foreground block truncate text-[11.5px]">{account.email}</span>
            </span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" side="top" className="w-60">
          <DropdownMenuLabel>{account.email}</DropdownMenuLabel>
          <DropdownMenuItem asChild>
            <Link href="/settings?tab=account">
              <UserRound /> Account settings
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setChangingPassword(true)}>
            <KeyRound /> Change password
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Theme</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={preference} onValueChange={(next) => setTheme(parseTheme(next))}>
            <DropdownMenuRadioItem value="light">
              <Sun /> Light
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="dark">
              <Moon /> Dark
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="system">
              <Monitor /> System
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => void signOut()}>
            <LogOut /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <PasswordDialog open={changingPassword} onOpenChange={setChangingPassword} />
    </>
  );
}
