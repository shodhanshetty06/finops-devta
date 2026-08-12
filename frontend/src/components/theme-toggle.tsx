"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // Avoids a server/client mismatch: next-themes can't know the user's
  // system preference during SSR, so the icon only renders after mount.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    // The canonical next-themes hydration-safe-mount pattern: resolvedTheme
    // is only known once mounted client-side, so the icon deliberately
    // renders one tick late rather than risk a server/client mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  if (!mounted) return <Button variant="ghost" size="icon" aria-label="Toggle theme" />;

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      {resolvedTheme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
