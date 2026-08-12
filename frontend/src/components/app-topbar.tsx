"use client";

import { Bell, LogOut, Menu, Settings, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

import { CommandMenu } from "@/components/command-menu";
import { CurrencySwitcher } from "@/components/currency-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Breadcrumbs, type Crumb } from "@/components/ui/breadcrumbs";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ALL_NAV_ITEMS } from "@/lib/nav-items";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";

const ROLE_LABEL: Record<string, string> = { admin: "Admin", consultant: "Consultant", customer: "Customer" };

function buildBreadcrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return [{ label: "Dashboard" }];

  const navMatch = ALL_NAV_ITEMS.find((i) => i.href === pathname);
  if (navMatch) return [{ label: navMatch.label }];

  // Falls back to a readable trail for nested/dynamic routes (e.g.
  // /projects/12/estimates/3) - numeric segments render as "#12" rather
  // than a raw route param.
  const crumbs: Crumb[] = [];
  let href = "";
  for (const segment of segments) {
    href += `/${segment}`;
    const match = ALL_NAV_ITEMS.find((i) => i.href === href);
    const isNumeric = /^\d+$/.test(segment);
    crumbs.push({
      label: match ? match.label : isNumeric ? `#${segment}` : segment.charAt(0).toUpperCase() + segment.slice(1),
      href,
    });
  }
  return crumbs;
}

export function AppTopbar({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const breadcrumbs = useMemo(() => buildBreadcrumbs(pathname), [pathname]);

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-topbar px-4 backdrop-blur-sm sm:px-6">
      <button
        type="button"
        onClick={onOpenMobileNav}
        aria-label="Open navigation"
        className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
      >
        <Menu className="h-4.5 w-4.5" />
      </button>

      <div className="hidden min-w-0 flex-1 lg:block">
        <Breadcrumbs items={breadcrumbs} />
      </div>
      <div className="min-w-0 flex-1 lg:hidden">
        <p className="truncate text-sm font-semibold text-foreground">{breadcrumbs[breadcrumbs.length - 1]?.label}</p>
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <CommandMenu />

        <DropdownMenu>
          <DropdownMenuTrigger className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">
            <Bell className="h-4 w-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-72">
            <DropdownMenuLabel>Notifications</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <p className="px-2.5 py-6 text-center text-sm text-muted-foreground">You&apos;re all caught up.</p>
          </DropdownMenuContent>
        </DropdownMenu>

        <CurrencySwitcher />

        <ThemeToggle />

        <DropdownMenu>
          <DropdownMenuTrigger className="ml-1 flex items-center gap-2 rounded-full">
            <Avatar name={user?.full_name ?? "?"} size="sm" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-64">
            <div className="flex items-center gap-3 px-2.5 py-2">
              <Avatar name={user?.full_name ?? "?"} />
              <div className="flex min-w-0 flex-col">
                <p className="truncate text-sm font-medium text-foreground">{user?.full_name}</p>
                <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
              </div>
            </div>
            <div className="px-2.5 pb-2">
              <Badge variant="outline">{user ? (ROLE_LABEL[user.role] ?? user.role) : ""}</Badge>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <Link href="/settings" className="flex w-full items-center gap-2">
                <Settings className="h-4 w-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Link href="/settings" className="flex w-full items-center gap-2">
                <UserIcon className="h-4 w-4" />
                Profile
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={logout}>
              <LogOut className="h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Link href="/estimate/new" className={cn(buttonVariants({ size: "sm" }), "ml-1 hidden sm:inline-flex")}>
          New estimate
        </Link>
      </div>
    </header>
  );
}
