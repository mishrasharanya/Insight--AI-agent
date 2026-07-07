import { useEffect, useState } from "react";
import { Plus, Trash2, FolderTree, Play } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";

export default function Workspaces() {
  const [workspaces, setWorkspaces] = useState([]);
  const [folder, setFolder] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/workspaces");
      const list = Array.isArray(data) ? data : data?.workspaces || data?.folders || [];
      setWorkspaces(list);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to load workspaces");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    const path = folder.trim();
    if (!path) return;
    setBusy(true);
    try {
      await api.post("/workspaces", { folder: path });
      toast.success("Workspace added");
      setFolder("");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to add");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (path) => {
    if (!window.confirm(`Remove workspace "${path}"?`)) return;
    try {
      await api.delete("/workspaces", { data: { folder: path } });
      toast.success("Workspace removed");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to remove");
    }
  };

  const ingest = async () => {
    setBusy(true);
    try {
      await api.post("/ingest");
      toast.success("Ingestion triggered");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Ingest failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-8 py-10">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-heading text-3xl font-semibold text-zinc-900" data-testid="workspaces-title">Workspaces</h1>
          <p className="text-sm text-zinc-500 mt-2 max-w-xl">
            Folders on your machine (or on the agent) that will be indexed and made searchable by chat.
          </p>
        </div>
        <button
          onClick={ingest}
          disabled={busy}
          data-testid="workspaces-ingest-button"
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-zinc-900 rounded-md hover:bg-zinc-800 disabled:opacity-40 transition-colors"
        >
          <Play className="w-4 h-4" />
          Run ingest
        </button>
      </div>

      <form onSubmit={add} className="flex gap-3 mb-8">
        <input
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          placeholder="/path/to/folder"
          data-testid="workspaces-folder-input"
          className="flex-1 px-4 py-2.5 border border-zinc-200 rounded-md placeholder-zinc-400 focus:outline-none focus:ring-1 focus:ring-zinc-900 focus:border-zinc-900 text-sm bg-white"
        />
        <button
          type="submit"
          disabled={busy || !folder.trim()}
          data-testid="workspaces-add-button"
          className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-zinc-900 rounded-md hover:bg-zinc-800 disabled:opacity-40 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add
        </button>
      </form>

      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm" data-testid="workspaces-list">
        {loading ? (
          <div className="p-8 text-sm text-zinc-500 text-center">Loading…</div>
        ) : workspaces.length === 0 ? (
          <div className="p-12 text-center">
            <FolderTree className="w-8 h-8 mx-auto text-zinc-400 mb-3" strokeWidth={1.5} />
            <p className="text-sm text-zinc-500">No workspaces yet. Add a folder path to get started.</p>
          </div>
        ) : (
          <ul>
            {workspaces.map((w, i) => {
              const path = typeof w === "string" ? w : w.folder || w.path || JSON.stringify(w);
              return (
                <li
                  key={`${path}-${i}`}
                  className="flex items-center justify-between px-6 py-4 border-b border-zinc-100 last:border-0"
                  data-testid={`workspace-row-${i}`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FolderTree className="w-4 h-4 text-zinc-500 shrink-0" strokeWidth={1.75} />
                    <span className="text-sm text-zinc-900 truncate font-mono">{path}</span>
                  </div>
                  <button
                    onClick={() => remove(path)}
                    data-testid={`workspace-remove-${i}`}
                    className="p-2 rounded-md text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                    aria-label="Remove"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}