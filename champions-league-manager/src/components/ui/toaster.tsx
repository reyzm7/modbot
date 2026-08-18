"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      theme="dark"
      position="bottom-right"
      closeButton
      duration={3600}
      toastOptions={{
        classNames: {
          toast:
            "!bg-[hsl(230_45%_9%/0.92)] !border !border-white/12 !backdrop-blur-xl !text-foreground !rounded-lg !shadow-glass",
          title: "!font-display !font-semibold !tracking-tight",
          description: "!text-muted-foreground",
          actionButton: "!bg-primary !text-primary-foreground",
          cancelButton: "!bg-white/10 !text-foreground",
        },
      }}
    />
  );
}
