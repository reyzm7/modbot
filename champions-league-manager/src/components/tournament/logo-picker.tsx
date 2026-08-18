"use client";

import { useId, useRef, useState } from "react";
import { ImagePlus, Loader2, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { readLogoFile } from "@/lib/utils";
import { cn } from "@/lib/utils";

type LogoPickerProps = {
  value?: string;
  onChange: (dataUrl: string) => void;
  onClear: () => void;
  label: string;
  size?: "sm" | "lg";
  className?: string;
};

export function LogoPicker({
  value,
  onChange,
  onClear,
  label,
  size = "sm",
  className,
}: LogoPickerProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setLoading(true);
    try {
      onChange(await readLogoFile(file));
    } catch (error) {
      toast.error("Logo non importé", {
        description: error instanceof Error ? error.message : "Format d'image non pris en charge.",
      });
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const box = size === "lg" ? "size-16" : "size-10";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(event) => void handleFile(event.target.files?.[0])}
      />

      <label
        htmlFor={inputId}
        aria-label={label}
        className={cn(
          "group relative grid cursor-pointer place-items-center overflow-hidden rounded-lg border border-dashed border-white/18 bg-white/[0.04] transition-colors hover:border-primary/50 hover:bg-white/[0.07] focus-within:ring-2 focus-within:ring-ring",
          box,
        )}
      >
        {loading ? (
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
        ) : value ? (
          <img src={value} alt="" className="size-full object-contain p-1" />
        ) : (
          <ImagePlus className="size-4 text-muted-foreground transition-colors group-hover:text-primary" />
        )}
      </label>

      {value ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={`Retirer ${label.toLowerCase()}`}
          onClick={onClear}
        >
          <X />
        </Button>
      ) : null}
    </div>
  );
}
