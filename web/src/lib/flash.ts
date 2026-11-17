/** Scroll to an element, open the <details> around it, focus its field and flash it: the one highlight every
 *  "fix this →" link and #anchor lands on (HashFlash in the layout, SetupKeys, PaidView, SettingsForm). */
export const FLASH = ["ring-2", "ring-accent", "ring-offset-4", "ring-offset-panel", "bg-accent/10"];

const timers = new WeakMap<HTMLElement, ReturnType<typeof setTimeout>>();

export function flash(el: HTMLElement, ms = 2500) {
  for (let d = el.closest("details"); d; d = d.parentElement?.closest("details") ?? null) d.open = true;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  const field = el.matches("input, textarea, select, button") ? el : el.querySelector<HTMLElement>("input, textarea, select");
  field?.focus({ preventScroll: true });
  const prev = timers.get(el);
  if (prev) clearTimeout(prev);
  el.classList.add(...FLASH);
  timers.set(el, setTimeout(() => { el.classList.remove(...FLASH); timers.delete(el); }, ms));
}

/** Flash the element with this id once it exists (pages that render after their data loads). */
export function flashId(id: string, waitMs = 4000) {
  const start = Date.now();
  const tick = () => {
    const el = document.getElementById(id);
    if (el) return flash(el);
    if (Date.now() - start < waitMs) setTimeout(tick, 100);
  };
  tick();
}
