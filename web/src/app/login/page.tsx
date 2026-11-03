export const metadata = { title: "Sign in" };

export default async function Login({ searchParams }: { searchParams: Promise<{ error?: string; next?: string }> }) {
  const { error, next } = await searchParams;
  return (
    <div className="mx-auto mt-16 max-w-sm rounded-2xl border border-line bg-panel p-6">
      <h1 className="text-xl font-bold">Sign in</h1>
      <p className="mt-1 text-sm text-muted">This dashboard is private.</p>
      <form action="/api/login" method="post" className="mt-5 space-y-3">
        <input type="hidden" name="next" value={next ?? "/"} />
        <input type="password" name="password" autoFocus required placeholder="Password"
          className="w-full rounded-lg border border-line bg-panel-2 px-3 py-2 outline-none focus:border-accent" />
        {error && <p className="text-sm text-mega">Wrong password.</p>}
        <button className="w-full rounded-lg bg-accent px-3 py-2 font-semibold text-ink hover:brightness-110">Enter</button>
      </form>
    </div>
  );
}
