import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { marked } from "marked";
import { isLocal, loadProfile, profileNames } from "@/lib/data";
import { deObsidian } from "@/lib/format";
import Dashboard from "@/components/Dashboard";

export async function generateStaticParams() {
  return (await profileNames()).map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }): Promise<Metadata> {
  return { title: (await params).name };
}

export default async function ProfilePage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const profile = await loadProfile(name);
  if (!profile) notFound();
  const ideas = profile.ideas.map((i) => ({
    date: i.date,
    file: i.file,
    html: marked.parse(deObsidian(i.markdown), { async: false }) as string,
  }));
  return <Dashboard profile={{ ...profile, ideas: [] }} ideas={ideas} local={isLocal} />;
}
