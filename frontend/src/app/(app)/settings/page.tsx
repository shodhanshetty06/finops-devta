"use client";

import { Check, Laptop, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/contexts/auth-context";
import { getDefaultNormalizationStrategy, setDefaultNormalizationStrategy } from "@/lib/preferences";
import { cn, formatDate } from "@/lib/utils";
import { NORMALIZATION_STRATEGIES, type NormalizationStrategy } from "@/lib/types";

const ROLE_LABEL: Record<string, string> = { admin: "Admin", consultant: "Consultant", customer: "Customer" };

const THEME_OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Laptop },
] as const;

export default function SettingsPage() {
  const { user } = useAuth();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [strategy, setStrategy] = useState<NormalizationStrategy>("balanced");

  useEffect(() => {
    // Reads localStorage (theme's resolved value, the saved strategy) -
    // both are external-system state unknown during SSR, so this
    // deliberately renders one tick late rather than risk a hydration
    // mismatch (the same pattern theme-toggle.tsx uses).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
    setStrategy(getDefaultNormalizationStrategy());
  }, []);

  function handleStrategyChange(value: NormalizationStrategy) {
    setStrategy(value);
    setDefaultNormalizationStrategy(value);
    toast.success("Default normalization strategy updated");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">Your profile, appearance, and local preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Account details from your session.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {user && (
            <div className="flex items-center gap-4">
              <Avatar name={user.full_name} size="lg" />
              <div className="flex flex-col gap-1">
                <p className="text-base font-medium text-foreground">{user.full_name}</p>
                <p className="text-sm text-muted-foreground">{user.email}</p>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{ROLE_LABEL[user.role] ?? user.role}</Badge>
                  <span className="text-xs text-muted-foreground">Member since {formatDate(user.created_at)}</span>
                </div>
              </div>
            </div>
          )}
          <Alert variant="info" title="Editing isn't available yet">
            There&apos;s no profile-update endpoint in this environment (auth only supports register/login/me) - contact
            your administrator for account changes.
          </Alert>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Applies immediately across the whole app.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {THEME_OPTIONS.map((opt) => {
              const isActive = mounted && theme === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setTheme(opt.value)}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-lg border p-4 text-sm transition-colors",
                    isActive ? "border-primary bg-primary-50 dark:bg-primary-950" : "border-border hover:bg-muted/40",
                  )}
                >
                  <span className="relative flex h-9 w-9 items-center justify-center rounded-full bg-muted">
                    <opt.icon className="h-4 w-4 text-foreground" />
                    {isActive && (
                      <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground">
                        <Check className="h-2.5 w-2.5" />
                      </span>
                    )}
                  </span>
                  <span className="font-medium text-foreground">{opt.label}</span>
                </button>
              );
            })}
          </div>
          {mounted && <p className="mt-3 text-xs text-muted-foreground">Currently resolved to: {resolvedTheme}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Estimate defaults</CardTitle>
          <CardDescription>Applied to new questionnaires and estimates you start - saved on this device only.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex max-w-xs flex-col gap-1.5">
            <Label htmlFor="default-strategy">Default normalization strategy</Label>
            <Select id="default-strategy" value={strategy} onChange={(e) => handleStrategyChange(e.target.value as NormalizationStrategy)}>
              {NORMALIZATION_STRATEGIES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
