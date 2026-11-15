import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { isLocal, loadProfile, profileNames } from "@/lib/data";
import Dashboard from "@/components/Dashboard";

export async function generateStaticParams() {
  return (await profileNames()).map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }): Promise<Metadata> {
  return { title: `Videos · ${(await params).name}` };
}

export default async function VideosPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const profile = await loadProfile(name);
  if (!profile) notFound();
  return <Dashboard profile={{ ...profile, ideas: [], swipe: [] }} local={isLocal} />;   // ideas and swipe live on their own tab
}
