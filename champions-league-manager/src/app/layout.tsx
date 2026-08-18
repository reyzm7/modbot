import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import { AmbientBackground } from "@/components/layout/ambient-background";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { StoreHydrator } from "@/components/layout/store-hydrator";
import { Toaster } from "@/components/ui/toaster";

import "./globals.css";

const inter = localFont({
  src: "../fonts/Inter.woff2",
  variable: "--font-inter",
  weight: "100 900",
  display: "swap",
});

const sora = localFont({
  src: "../fonts/Sora.woff2",
  variable: "--font-sora",
  weight: "100 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MrDarryl",
  description:
    "Le site de MrDarryl, streamer FIFA passionné de Carrière Manager et de Club Pro. Suivez les tournois, les scores et le classement en direct.",
  applicationName: "MrDarryl",
  authors: [{ name: "MrDarryl" }],
  keywords: ["MrDarryl", "FIFA", "Club Pro", "Carrière Manager", "tournoi", "streamer"],
  openGraph: {
    title: "MrDarryl",
    description: "Tournois FIFA en direct : scores, classement et phase finale.",
    type: "website",
    locale: "fr_FR",
    siteName: "MrDarryl",
  },
};

export const viewport: Viewport = {
  themeColor: "#05060F",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`dark ${inter.variable} ${sora.variable}`}>
      <body className="flex min-h-dvh flex-col font-sans">
        <AmbientBackground />
        <StoreHydrator />
        <SiteHeader />
        {children}
        <SiteFooter />
        <Toaster />
      </body>
    </html>
  );
}
