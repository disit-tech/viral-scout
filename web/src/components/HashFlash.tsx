"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { flashId } from "@/lib/flash";

/** Every page: landing on #something (a link from another page, a same-page link, back/forward) flashes that
 *  element. #key-… on the Setup page is left to SetupKeys, which also clears filters that hide the key. */
export default function HashFlash() {
  const pathname = usePathname();

  useEffect(() => {
    const run = () => {
      const id = decodeURIComponent(window.location.hash.slice(1));
      if (id && !id.startsWith("key-")) flashId(id);
    };
    run();                                         // arrived on this page (client navigation keeps the hash)
    window.addEventListener("hashchange", run);
    return () => window.removeEventListener("hashchange", run);
  }, [pathname]);

  useEffect(() => {
    // A click on a link to the hash the page already has fires no hashchange: flash anyway.
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
      const a = (e.target as HTMLElement).closest<HTMLAnchorElement>("a[href*='#']");
      if (!a) return;
      const url = new URL(a.href, window.location.href);
      if (url.pathname !== window.location.pathname || url.hash !== window.location.hash) return;
      const id = decodeURIComponent(url.hash.slice(1));
      if (id && !id.startsWith("key-")) flashId(id);
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);
  return null;
}
