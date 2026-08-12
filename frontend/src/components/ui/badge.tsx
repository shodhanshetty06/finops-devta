import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium leading-4 [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary-50 text-primary-800 dark:bg-primary-950 dark:text-primary-300",
        secondary: "border-transparent bg-muted text-muted-foreground",
        success: "border-transparent bg-success-50 text-success-700 dark:bg-success-900/40 dark:text-success-200",
        warning: "border-transparent bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-200",
        destructive: "border-transparent bg-error-50 text-error-700 dark:bg-error-900/40 dark:text-error-200",
        outline: "border-border-strong text-foreground bg-transparent",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
