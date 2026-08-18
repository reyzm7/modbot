"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Check, Lock } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { useStepAccess } from "@/hooks/use-tournament";
import { STEPS, stepIndex, type StepId } from "@/lib/steps";
import { cn } from "@/lib/utils";

export function StepRail({ current }: { current: StepId }) {
  const access = useStepAccess();
  const currentIndex = stepIndex(current);
  const percent = ((currentIndex + 1) / STEPS.length) * 100;

  return (
    <div className="w-full">
      <div className="mb-2 flex items-baseline justify-between gap-4 sm:hidden">
        <p className="eyebrow">
          Étape {currentIndex + 1} / {STEPS.length}
        </p>
        <p className="font-display text-sm font-semibold">{STEPS[currentIndex].label}</p>
      </div>

      <nav aria-label="Progression du tournoi" className="hidden sm:block">
        <ol className="flex items-center gap-1">
          {STEPS.map((step, index) => {
            const done = index < currentIndex;
            const active = index === currentIndex;
            const unlocked = access[step.id];

            const content = (
              <span className="relative z-10 inline-flex items-center gap-2">
                <span
                  className={cn(
                    "grid size-5 shrink-0 place-items-center rounded-full border text-[10px] font-bold transition-colors",
                    active && "border-primary bg-primary text-primary-foreground",
                    done && "border-mint/50 bg-mint/15 text-mint",
                    !active && !done && "border-white/15 text-muted-foreground",
                  )}
                >
                  {done ? (
                    <Check className="size-3" strokeWidth={3} />
                  ) : unlocked || active ? (
                    index + 1
                  ) : (
                    <Lock className="size-2.5" />
                  )}
                </span>
                <span className="hidden lg:inline">{step.label}</span>
                <span className="lg:hidden">{step.short}</span>
              </span>
            );

            const className = cn(
              "relative inline-flex items-center rounded-md px-2.5 py-1.5 font-display text-xs font-semibold tracking-tight transition-colors",
              active ? "text-foreground" : "text-muted-foreground",
              unlocked && !active && "hover:text-foreground",
              !unlocked && !active && "cursor-not-allowed opacity-55",
            );

            return (
              <li key={step.id} className="flex items-center">
                {unlocked ? (
                  <Link href={step.href} className={className} aria-current={active ? "step" : undefined}>
                    {active ? (
                      <motion.span
                        layoutId="step-rail-active"
                        className="absolute inset-0 rounded-md border border-white/12 bg-white/[0.07]"
                        transition={{ type: "spring", stiffness: 380, damping: 34 }}
                      />
                    ) : null}
                    {content}
                  </Link>
                ) : (
                  <span className={className} aria-disabled="true">
                    {content}
                  </span>
                )}
                {index < STEPS.length - 1 ? (
                  <span aria-hidden className="mx-0.5 h-px w-3 bg-white/12 lg:w-4" />
                ) : null}
              </li>
            );
          })}
        </ol>
      </nav>

      <Progress
        value={percent}
        className="mt-2 sm:mt-3"
        label={`Étape ${currentIndex + 1} sur ${STEPS.length}`}
      />
    </div>
  );
}
