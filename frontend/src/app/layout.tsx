import type { Metadata } from "next";
import { Toaster } from "sonner";

import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from "@/contexts/auth-context";
import { CurrencyProvider } from "@/contexts/currency-context";
import { QueryProvider } from "@/lib/query-client";

import "./globals.css";

export const metadata: Metadata = {
  title: "GCP FinOps Estimation Platform",
  description: "AI-powered Google Cloud FinOps estimation & pricing platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className="h-full">
      <body className="h-full antialiased" suppressHydrationWarning>
        <ThemeProvider>
          <QueryProvider>
            <CurrencyProvider>
              <AuthProvider>
                {children}
                <Toaster
                  richColors
                  position="top-right"
                  toastOptions={{
                    classNames: {
                      toast: "!rounded-lg !border !border-border !bg-surface-raised !text-foreground !shadow-lg",
                    },
                  }}
                />
              </AuthProvider>
            </CurrencyProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
