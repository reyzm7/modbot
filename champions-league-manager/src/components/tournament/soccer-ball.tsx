"use client";

import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

/**
 * Ballon stylisé. `rolling` combine rotation et rebond : c'est ce mélange qui
 * donne l'impression d'un ballon qui roule plutôt que d'une icône qui tourne.
 */
export function SoccerBall({
  className,
  rolling = false,
}: {
  className?: string;
  rolling?: boolean;
}) {
  const ball = (
    <svg viewBox="0 0 100 100" className={cn("size-full", className)} aria-hidden focusable="false">
      <circle cx="50" cy="50" r="46" className="fill-white" />
      <circle cx="50" cy="50" r="46" className="fill-none stroke-[#0B1030]" strokeWidth="3" />
      <polygon points="50,26 65,37 59,55 41,55 35,37" className="fill-[#0B1030]" />
      <g className="stroke-[#0B1030]" strokeWidth="3.5" strokeLinecap="round" fill="none">
        <path d="M50 26 L50 5" />
        <path d="M65 37 L85 27" />
        <path d="M59 55 L72 74" />
        <path d="M41 55 L28 74" />
        <path d="M35 37 L15 27" />
      </g>
      <path
        d="M22 78 Q50 92 78 78"
        className="stroke-[#0B1030]"
        strokeWidth="3"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );

  if (!rolling) return <span className={cn("block", className)}>{ball}</span>;

  return (
    <motion.span
      className={cn("block", className)}
      animate={{ rotate: 360, y: [0, -7, 0] }}
      transition={{
        rotate: { duration: 1.1, repeat: Infinity, ease: "linear" },
        y: { duration: 0.55, repeat: Infinity, ease: "easeInOut" },
      }}
    >
      {ball}
    </motion.span>
  );
}
