"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, UsageSummary } from "../../lib/api";
import { BackToChat } from "../../components/BackToChat";

export default function AdminPage() {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);
  const [summary, setSummary] = useState<{ last_7_days: UsageSummary; last_30_days: UsageSummary } | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [tokens, setTokens] = useState("");
  const [days, setDays] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [notifyUser, setNotifyUser] = useState(true);
  const [llmResult, setLlmResult] = useState("");

  useEffect(() => {
    void api.adminMe().then(async () => {
      setAllowed(true);
      void api.adminUsageSummary().then(setSummary).catch(() => undefined);
    }).catch(() => router.replace("/"));
  }, [router]);

  async function grant() {
    setBusy(true);
    setMessage("");
    try {
      await api.adminGrant(email.trim(), Number(tokens || 0), Number(days || 0), note.trim(), notifyUser);
      setMessage("Credits granted.");
      setEmail(""); setTokens(""); setDays(""); setNote("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Grant failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!allowed) return <div className="flex h-full items-center justify-center"><div className="h-10 w-10 animate-spin rounded-full border-2 border-white/20 border-t-white" /></div>;
  return <div className="app-page h-full overflow-y-auto text-white">
    <div className="app-page-inner mx-auto max-w-5xl">
      <div className="flex items-start justify-between gap-4"><h1 className="text-3xl font-semibold">Admin dashboard</h1><BackToChat className="rounded-lg border px-3 py-2 text-sm backdrop-blur" /></div>
      {summary && <section className="app-row mt-6 grid gap-4 p-5 sm:grid-cols-2">
        <div><p className="text-sm text-slate-300">Answers in 7 days</p><p className="text-2xl font-semibold">{summary.last_7_days.answers}</p></div>
        <div><p className="text-sm text-slate-300">Answers in 30 days</p><p className="text-2xl font-semibold">{summary.last_30_days.answers}</p></div>
      </section>}
      <section className="app-row mt-6 p-5">
        <h2 className="text-xl font-semibold">LLM provider</h2>
        <button disabled={busy} onClick={async () => {
          setBusy(true);
          try {
            const result = await api.adminLlmTest();
            setLlmResult(`${result.provider} / ${result.model}: ${result.ok ? "OK" : "Failed"}; tool call: ${result.tool_calls_ok ? "OK" : "Failed"} (${result.latency_ms} ms)`);
          } catch (error) {
            setLlmResult(error instanceof Error ? error.message : "LLM test failed.");
          } finally {
            setBusy(false);
          }
        }} className="mt-4 rounded-lg bg-white px-4 py-2 font-semibold text-slate-950 disabled:opacity-50">Test LLM provider</button>
        {llmResult && <p role="status" className="mt-3 text-sm text-slate-300">{llmResult}</p>}
      </section>
      <section className="app-row mt-6 p-5">
        <h2 className="text-xl font-semibold">Manual credit grant</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <input value={email} onChange={event => setEmail(event.target.value)} placeholder="User email" className="rounded-lg border border-white/15 bg-slate-950 px-3 py-3" />
          <input value={tokens} onChange={event => setTokens(event.target.value)} inputMode="numeric" placeholder="Credits" className="rounded-lg border border-white/15 bg-slate-950 px-3 py-3" />
          <input value={days} onChange={event => setDays(event.target.value)} inputMode="numeric" placeholder="Premium days" className="rounded-lg border border-white/15 bg-slate-950 px-3 py-3" />
          <input value={note} onChange={event => setNote(event.target.value)} placeholder="Note" className="rounded-lg border border-white/15 bg-slate-950 px-3 py-3" />
        </div>
        <label className="mt-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={notifyUser} onChange={event => setNotifyUser(event.target.checked)} /> Email user</label>
        <button disabled={busy} onClick={() => void grant()} className="mt-4 rounded-lg bg-white px-4 py-2 font-semibold text-slate-950 disabled:opacity-50">{busy ? "Granting..." : "Grant credits"}</button>
        {message && <p role="status" className="mt-3 text-sm text-slate-300">{message}</p>}
      </section>
    </div>
  </div>;
}
