"use client";

import { AlertOctagon, RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  error: Error | null;
}

/** Catches render/lifecycle errors in its subtree so one broken panel
 * (e.g. a chart choking on an unexpected value) can't take down the whole
 * page. Framer Motion / async errors inside event handlers aren't caught by
 * React error boundaries by design - this only guards render errors. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-error-200 bg-error-50 px-6 py-12 text-center dark:border-error-900 dark:bg-error-900/20">
          <AlertOctagon className="h-6 w-6 text-error-600 dark:text-error-400" />
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium text-foreground">{this.props.fallbackTitle ?? "Something went wrong rendering this section"}</p>
            <p className="max-w-md text-sm text-muted-foreground">{this.state.error.message}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => this.setState({ error: null })}>
            <RotateCcw className="h-3.5 w-3.5" />
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
