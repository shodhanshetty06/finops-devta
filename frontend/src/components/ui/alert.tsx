import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

const VARIANTS = {
  info: {
    icon: Info,
    classes: "border-primary-200 bg-primary-50 text-primary-900 dark:border-primary-900 dark:bg-primary-950 dark:text-primary-200",
    iconClasses: "text-primary-600 dark:text-primary-400",
  },
  success: {
    icon: CheckCircle2,
    classes: "border-success-200 bg-success-50 text-success-900 dark:border-success-900 dark:bg-success-900/30 dark:text-success-200",
    iconClasses: "text-success-600 dark:text-success-400",
  },
  warning: {
    icon: AlertTriangle,
    classes: "border-warning-200 bg-warning-50 text-warning-900 dark:border-warning-900 dark:bg-warning-900/30 dark:text-warning-200",
    iconClasses: "text-warning-600 dark:text-warning-400",
  },
  error: {
    icon: XCircle,
    classes: "border-error-200 bg-error-50 text-error-900 dark:border-error-900 dark:bg-error-900/30 dark:text-error-200",
    iconClasses: "text-error-600 dark:text-error-400",
  },
} as const;

export function Alert({
  variant = "info",
  title,
  children,
  className,
}: {
  variant?: keyof typeof VARIANTS;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const { icon: Icon, classes, iconClasses } = VARIANTS[variant];
  return (
    <div role="alert" className={cn("flex gap-3 rounded-lg border p-4 text-sm", classes, className)}>
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", iconClasses)} />
      <div className="flex flex-col gap-0.5">
        {title && <p className="font-medium leading-tight">{title}</p>}
        {children && <div className="leading-relaxed opacity-90">{children}</div>}
      </div>
    </div>
  );
}
