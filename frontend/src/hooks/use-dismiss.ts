"use client";

import { useEffect, type RefObject } from "react";

/** Fires `onEscape` when Escape is pressed while `active`. Shared by every
 * hand-rolled overlay primitive (Dialog, Sheet, DropdownMenu, CommandMenu)
 * instead of a Radix dependency - this project intentionally hand-rolls its
 * UI primitives (see components/ui/button.tsx and friends), so overlays
 * follow the same convention. */
export function useEscapeKey(active: boolean, onEscape: () => void) {
  useEffect(() => {
    if (!active) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onEscape();
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [active, onEscape]);
}

/** Fires `onOutside` on a pointerdown outside every ref in `refs`. Used to
 * close dropdowns/popovers when clicking elsewhere on the page. */
export function useClickOutside(refs: RefObject<HTMLElement | null>[], active: boolean, onOutside: () => void) {
  useEffect(() => {
    if (!active) return;
    function handler(e: PointerEvent) {
      const target = e.target as Node;
      if (refs.some((ref) => ref.current?.contains(target))) return;
      onOutside();
    }
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [refs, active, onOutside]);
}

/** Locks page scroll while `active` (dialogs/sheets/drawers) - restores the
 * previous overflow value on cleanup so nesting doesn't clobber it. */
export function useScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [active]);
}
