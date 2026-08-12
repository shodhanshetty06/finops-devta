import { Cloud, ShieldCheck, Sparkles, TrendingDown } from "lucide-react";
import Link from "next/link";

const HIGHLIGHTS = [
  { icon: Sparkles, text: "AI-assisted requirement intake from a questionnaire, spreadsheet, or free text" },
  { icon: ShieldCheck, text: "Every assumption and validation result logged - nothing changed silently" },
  { icon: TrendingDown, text: "Real Google Cloud Billing Catalog pricing, never a hand-rolled estimate" },
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh grid-cols-1 bg-background lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-slate-950 p-10 text-white lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
            backgroundSize: "28px 28px",
          }}
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -top-24 -right-24 h-96 w-96 rounded-full bg-primary-600/30 blur-3xl"
          aria-hidden="true"
        />

        <Link href="/" className="relative flex items-center gap-2 text-lg font-semibold">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-600">
            <Cloud className="h-4.5 w-4.5" />
          </span>
          GCP FinOps
        </Link>

        <div className="relative flex max-w-md flex-col gap-8">
          <blockquote className="flex flex-col gap-3">
            <p className="text-2xl font-semibold leading-snug tracking-tight">
              &ldquo;Price any Google Cloud architecture with full transparency into every assumption made.&rdquo;
            </p>
            <cite className="text-sm not-italic text-slate-400">The AI-powered FinOps estimation platform</cite>
          </blockquote>

          <ul className="flex flex-col gap-4">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-sm text-slate-300">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/10">
                  <Icon className="h-3.5 w-3.5" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-slate-500">© {new Date().getFullYear()} GCP FinOps Estimation Platform</p>
      </div>

      <div className="flex flex-col items-center justify-center px-6 py-10 sm:px-10">
        <Link href="/" className="mb-8 flex items-center gap-2 text-lg font-semibold text-foreground lg:hidden">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Cloud className="h-4.5 w-4.5" />
          </span>
          GCP FinOps
        </Link>
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
