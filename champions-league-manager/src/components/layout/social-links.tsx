import { MessageCircle, MonitorPlay, Music2, PlayCircle } from "lucide-react";

const NETWORKS = [
  {
    label: "Twitch",
    handle: "monsieurdarryl",
    href: "https://www.twitch.tv/monsieurdarryl",
    icon: MonitorPlay,
    accent: "hover:border-[#9146FF]/50 hover:text-[#B78CFF]",
  },
  {
    label: "YouTube",
    handle: "@monsieurdarryl",
    href: "https://youtube.com/@monsieurdarryl",
    icon: PlayCircle,
    accent: "hover:border-[#FF0033]/45 hover:text-[#FF6B85]",
  },
  {
    label: "Discord",
    handle: "Rejoindre le serveur",
    href: "https://discord.gg/R86rZwHDF",
    icon: MessageCircle,
    accent: "hover:border-[#5865F2]/50 hover:text-[#93A0FF]",
  },
  {
    label: "TikTok",
    handle: "@mrdarryl_clip",
    href: "https://www.tiktok.com/@mrdarryl_clip",
    icon: Music2,
    accent: "hover:border-[#25F4EE]/45 hover:text-[#7BF7F2]",
  },
];

export function SocialLinks() {
  return (
    <section className="mt-12" aria-labelledby="reseaux">
      <div className="glass surface-sheen p-6 text-center sm:p-8">
        <h2 id="reseaux" className="font-display text-lg font-bold tracking-tight">
          Retrouvez MrDarryl en direct
        </h2>
        <p className="mx-auto mt-2.5 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Streamer FIFA passionné de Carrière Manager et de Club Pro, MrDarryl réunit une
          communauté fidèle autour d&apos;une ambiance bienveillante, où l&apos;on vient autant pour
          le jeu que pour la bonne humeur. Rejoignez les lives, les clips et les tournois.
        </p>

        <ul className="mt-6 grid gap-2 sm:grid-cols-2">
          {NETWORKS.map((network) => (
            <li key={network.label}>
              <a
                href={network.href}
                target="_blank"
                rel="noopener noreferrer"
                className={`card-lift flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.04] px-4 py-3 text-left ${network.accent}`}
              >
                <network.icon className="size-5 shrink-0" />
                <span className="min-w-0">
                  <span className="block font-display text-sm font-bold tracking-tight">
                    {network.label}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {network.handle}
                  </span>
                </span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
