"use client";

import { AnimatePresence, motion } from "framer-motion";

import { cn } from "@/lib/utils";

/** Chiffre qui bascule comme un panneau de stade quand le score change. */
function Digit({ value }: { value: number | null }) {
  return (
    <span className="relative inline-grid h-[1.15em] min-w-[0.72em] place-items-center overflow-hidden align-middle">
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={value === null ? "empty" : value}
          initial={{ y: "-105%", opacity: 0 }}
          animate={{ y: "0%", opacity: 1 }}
          exit={{ y: "105%", opacity: 0 }}
          transition={{ type: "spring", stiffness: 420, damping: 32 }}
          className="tabular"
        >
          {value === null ? "–" : value}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function ScoreFlip({
  home,
  away,
  className,
}: {
  home: number | null;
  away: number | null;
  className?: string;
}) {
  const played = home !== null && away !== null;

  return (
    <motion.span
      // Un bref éclat au changement : le viewer voit le but tomber.
      key={`${home}-${away}`}
      initial={{ boxShadow: "0 0 0 0 hsl(152 60% 52% / 0)" }}
      animate={
        played
          ? {
              boxShadow: [
                "0 0 0 0 hsl(152 60% 52% / 0.45)",
                "0 0 0 7px hsl(152 60% 52% / 0)",
              ],
            }
          : {}
      }
      transition={{ duration: 0.7, ease: "easeOut" }}
      className={cn(
        "shrink-0 rounded-md border px-2.5 py-1 font-display text-sm font-bold",
        played ? "border-white/12 bg-white/[0.06]" : "border-white/8 text-muted-foreground",
        className,
      )}
    >
      <Digit value={home} />
      <span className="mx-1 opacity-50">–</span>
      <Digit value={away} />
    </motion.span>
  );
}
