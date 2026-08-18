"use client";

import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type StepNavProps = {
  backHref?: string;
  backLabel?: string;
  nextHref?: string;
  nextLabel?: string;
  nextDisabled?: boolean;
  /** Explains why the user cannot move on yet. */
  hint?: string;
  onNext?: () => void;
  className?: string;
};

export function StepNav({
  backHref,
  backLabel = "Retour",
  nextHref,
  nextLabel = "Suivant",
  nextDisabled = false,
  hint,
  onNext,
  className,
}: StepNavProps) {
  const showNext = Boolean(nextHref || onNext);

  return (
    <div
      className={cn(
        "sticky bottom-0 z-30 -mx-4 mt-10 border-t border-white/10 bg-[hsl(234_50%_4%/0.82)] px-4 py-3 backdrop-blur-xl sm:-mx-6 sm:px-6",
        className,
      )}
    >
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4">
        {backHref ? (
          <Button asChild variant="ghost" size="sm">
            <Link href={backHref}>
              <ArrowLeft />
              {backLabel}
            </Link>
          </Button>
        ) : (
          <span />
        )}

        <div className="flex items-center gap-3">
          {hint ? (
            <p className="hidden max-w-xs text-right text-xs text-muted-foreground sm:block">
              {hint}
            </p>
          ) : null}

          {showNext ? (
            nextHref && !nextDisabled && !onNext ? (
              <Button asChild size="sm">
                <Link href={nextHref}>
                  {nextLabel}
                  <ArrowRight />
                </Link>
              </Button>
            ) : (
              <Button size="sm" disabled={nextDisabled} onClick={onNext}>
                {nextLabel}
                <ArrowRight />
              </Button>
            )
          ) : null}
        </div>
      </div>

      {hint ? (
        <p className="mx-auto mt-2 max-w-5xl text-right text-xs text-muted-foreground sm:hidden">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
