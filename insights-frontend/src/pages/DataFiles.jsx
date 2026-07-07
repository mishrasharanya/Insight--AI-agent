import { useEffect, useState } from "react";
import { Table2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";

export default function DataFiles() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/privacy/inventory");
      const list = (data?.sources || []).map((s) => ({
        filename: s.filename,
        chunks: s.chunk_count,
        last: s.last_ingested,
      }));
      setFiles(list);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-heading text-4xl" data-testid="data-title">Synced files</h1>
          <p className="text-sm text-[#1a1a1a]/70 mt-2">
            Everything the agent has indexed from your Drive and Calendar.
          </p>
        </div>
        <button
          onClick={load}
          data-testid="data-refresh"
          className="inline-flex items-center gap-2 px-3 py-2 text-sm border border-[#1a1a1a]/20 hover:border-[#1a1a1a] transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-[#1a1a1a]/60">Loading…</p>
      ) : files.length === 0 ? (
        <div className="bg-white/50 border border-[#1a1a1a]/10 p-12 text-center">
          <Table2 className="w-8 h-8 mx-auto text-[#1a1a1a]/40 mb-3" strokeWidth={1.5} />
          <p className="text-sm text-[#1a1a1a]/60">
            Nothing synced yet. Go to Sync to add Calendar or Drive files.
          </p>
        </div>
      ) : (
        <div className="bg-white/50 border border-[#1a1a1a]/10" data-testid="data-list">
          <div className="grid grid-cols-[1fr_100px_180px] px-6 py-3 border-b border-[#1a1a1a]/10 font-mono text-[10px] uppercase tracking-widest text-[#1a1a1a]/60">
            <span>File</span><span>Chunks</span><span>Last ingested</span>
          </div>
          {files.map((f, i) => (
            <div key={i} data-testid={`data-row-${i}`}
                 className="grid grid-cols-[1fr_100px_180px] px-6 py-3 border-b border-[#1a1a1a]/5 last:border-0 items-center">
              <span className="text-sm truncate">{f.filename}</span>
              <span className="font-mono text-xs text-[#b8541f]">{f.chunks}</span>
              <span className="font-mono text-[11px] text-[#1a1a1a]/60">
                {f.last ? new Date(f.last).toLocaleString() : "—"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}