"use client";

import { useParams } from "next/navigation";

import { VisitorView } from "@/components/visitor/visitor-view";

export default function VisitorPage() {
  const params = useParams<{ slug: string }>();
  const slug = typeof params?.slug === "string" ? params.slug : "";

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
      <VisitorView slug={slug} />
    </main>
  );
}
