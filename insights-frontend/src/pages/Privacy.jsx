import { useEffect, useState } from "react";
import { ShieldCheck, AlertTriangle, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";

export default function Privacy() {
  const [inventory, setInventory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [purging, setPurging] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/privacy/inventory");
      setInventory(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to load inventory");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const purge = async () => {
    if (!window.confirm("This will delete all ingested data. Continue?")) return;
    setPurging(true);
    try {
      await api.post("/privacy/purge");
      toast.success("All data purged");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Purge failed");
    } finally {
      setPurging(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-8 py-10">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-heading text-3xl font-semibold text-zinc-900" data-testid="privacy-title">Privacy</h1>
          <p className="text-sm text-zinc-500 mt-2 max-w-xl">
            Everything the agent has stored about you. Purge it any time.
          </p>
        </div>
        <button
          onClick={load}
          data-testid="privacy-refresh-button"
          className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-zinc-900 bg-white border border-zinc-200 rounded-md hover:bg-zinc-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <section className="bg-white rounded-xl border border-zinc-200 p-6 mb-6" data-testid="privacy-inventory-card">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck className="w-4 h-4 text-zinc-500" strokeWidth={1.75} />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">Inventory</h3>
        </div>
        {loading ? (
          <p className="text-sm text-zinc-500">Loading…</p>
        ) : !inventory ? (
          <p className="text-sm text-zinc-500">Nothing to show.</p>
        ) : (
          <InventoryView data={inventory} />
        )}
      </section>

      <section className="bg-red-50 rounded-xl border border-red-100 p-6" data-testid="privacy-purge-card">
        <div className="flex items-start gap-4">
          <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5" strokeWidth={1.75} />
          <div className="flex-1">
            <h3 className="text-base font-semibold text-red-900">Purge all data</h3>
            <p className="text-sm text-red-700/80 mt-1">
              Permanently delete everything the agent has ingested about you. This cannot be undone.
            </p>
            <button
              onClick={purge}
              disabled={purging}
              data-testid="privacy-purge-button"
              className="mt-4 inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-40 transition-colors"
            >
              {purging ? "Purging…" : "Purge everything"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function InventoryView({ data }) {
  if (data && typeof data === "object" && !Array.isArray(data)) {
    const entries = Object.entries(data);
    const allScalars = entries.every(([, v]) => typeof v !== "object" || v === null);
    if (allScalars && entries.length <= 12) {
      return (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {entries.map(([k, v]) => (
            <div key={k} className="bg-zinc-50 rounded-md p-4">
              <p className="text-xs text-zinc-500 uppercase tracking-wider">{k}</p>
              <p className="text-2xl font-heading font-semibold text-zinc-900 mt-1">
                {v == null ? "—" : String(v)}
              </p>
            </div>
          ))}
        </div>
      );
    }
  }
  return (
    <pre className="text-xs bg-zinc-50 rounded-md p-4 overflow-x-auto max-h-96 text-zinc-700">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}