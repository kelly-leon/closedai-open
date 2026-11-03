"use client";

import { useEffect, useState } from "react";
import { BackToChat } from "../../components/BackToChat";
import { api, Usage } from "../../lib/api";

export default function CreditsPage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "CONTACT_EMAIL";

  async function refresh() { setUsage(await api.usage()); }
  useEffect(() => { void refresh(); }, []);

  async function redeem() {
    setBusy(true);
    setMessage("");
    try {
      await api.redeem(code.trim());
      setCode("");
      await refresh();
      setMessage("Code redeemed successfully.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "That code could not be redeemed.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="app-page h-full overflow-y-auto text-white">
    <div className="app-page-inner mx-auto max-w-3xl">
      <div className="flex items-start justify-between gap-4"><h1 className="text-3xl font-semibold">Credits</h1><BackToChat className="rounded-lg border px-3 py-2 text-sm backdrop-blur" /></div>
      <section className="app-row mt-8 p-5">
        <p className="text-sm text-slate-300">Balance</p>
        <p className="mt-1 text-4xl font-semibold">{usage ? usage.tokens_available ?? usage.token_balance ?? 0 : "..."}</p>
        {usage?.trial_resets_at && <p className="mt-2 text-sm text-slate-300">Weekly reset: {new Date(usage.trial_resets_at).toLocaleString()}</p>}
      </section>
      <section className="app-row mt-5 p-5">
        <h2 className="text-lg font-semibold">Redeem a code</h2>
        <div className="mt-3 flex gap-3">
          <input value={code} onChange={event => setCode(event.target.value.toUpperCase())} className="min-w-0 flex-1 rounded-lg border border-white/15 bg-slate-950 px-3 py-3" placeholder="Enter redeem code" />
          <button disabled={busy || !code.trim()} onClick={() => void redeem()} className="rounded-lg bg-white px-4 font-semibold text-slate-950 disabled:opacity-50">{busy ? "Redeeming..." : "Redeem"}</button>
        </div>
        {message && <p role="status" className="mt-3 text-sm text-slate-300">{message}</p>}
      </section>
      <p className="mt-5 text-sm text-slate-300">Need more credits? Contact <a className="text-sky-300 underline" href={`mailto:${contactEmail}`}>{contactEmail}</a></p>
    </div>
  </div>;
}
