"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-display text-sm font-semibold tracking-tight transition-all duration-200 disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-b from-primary to-[hsl(223_100%_50%)] text-primary-foreground shadow-[0_10px_30px_-12px_hsl(223_100%_59%/0.9)] hover:brightness-110",
        secondary:
          "border border-white/12 bg-white/[0.06] text-foreground backdrop-blur-xl hover:bg-white/[0.11]",
        outline:
          "border border-white/15 bg-transparent text-foreground hover:border-white/25 hover:bg-white/[0.05]",
        ghost: "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground",
        destructive:
          "bg-destructive/90 text-destructive-foreground hover:bg-destructive shadow-[0_10px_30px_-14px_hsl(351_80%_58%/0.9)]",
        trophy:
          "bg-gradient-to-b from-[hsl(45_80%_74%)] to-[hsl(41_62%_50%)] text-[#2A1D02] shadow-trophy hover:brightness-105",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-sm px-3 text-xs",
        lg: "h-12 rounded-lg px-6 text-base",
        icon: "size-10",
        "icon-sm": "size-8 rounded-sm",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
