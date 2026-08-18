import { ExternalLink } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-white/10 py-6">
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-1.5 px-4 text-center sm:px-6">
        <p className="text-xs text-muted-foreground">
          Développé par <span className="text-foreground/80">buffleboys</span> en partenariat avec{" "}
          <span className="text-foreground/80">ModBot</span>
        </p>
        <a
          href="https://discord.gg/FhU666gtQ"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-primary transition-colors hover:text-primary/80"
        >
          Rejoindre le Discord
          <ExternalLink className="size-3" />
        </a>
      </div>
    </footer>
  );
}
