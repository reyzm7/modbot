import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-display text-[10px] font-semibold uppercase tracking-[0.14em] transition-colors",
  {
    variants: {
      variant: {
        default: "border-primary/40 bg-primary/15 text-primary-foreground/90",
        neutral: "border-white/12 bg-white/[0.05] text-muted-foreground",
        success: "border-mint/40 bg-mint/12 text-mint",
        danger: "border-rose/40 bg-rose/12 text-rose",
        trophy: "border-champagne/45 bg-champagne/12 text-champagne",
        violet: "border-accent/45 bg-accent/15 text-[hsl(258_90%_82%)]",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
