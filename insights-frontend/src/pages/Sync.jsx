import { useState } from "react";
import { Calendar, HardDrive, X } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";

export default function Sync() {
  const [syncingCal, setSyncingCal] = useState(false);
  const [syncingDrive, setSyncingDrive] = useState(false);
  const [picked, setPicked] = useState([]);

  const syncCalendar = async () => {
    setSyncingCal(true);
    try {
      const { data } = await api.post("/sync/calendar", {});
      toast.success(`Calendar: ${data.events_synced} events, ${data.chunks_added} chunks`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Calendar sync failed");
    } finally { setSyncingCal(false); }
  };


  const openPicker = async () => {
    try {
      const { data: tokenInfo } = await api.get("/auth/google/picker-token");
      await new Promise((resolve) => window.gapi.load("picker", { callback: resolve }));

      const view = new window.google.picker.DocsView()
        .setIncludeFolders(true)
        .setSelectFolderEnabled(false);

      const picker = new window.google.picker.PickerBuilder()
        .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
        .addView(view)
        .setOAuthToken(tokenInfo.access_token)
        .setDeveloperKey(tokenInfo.developer_key)
        .setAppId(tokenInfo.app_id)
        .setCallback((res) => {
          if (res.action === window.google.picker.Action.PICKED) {
            const files = res.docs.map((d) => ({
              id: d.id, name: d.name, mimeType: d.mimeType,
            }));
            setPicked((p) => [...p, ...files]);
          }
        })
        .build();
      picker.setVisible(true);
    } catch (err) {
      toast.error(err?.response?.data?.detail || err.message || "Picker failed");
    }
  };

  const removePicked = (id) => setPicked((p) => p.filter((f) => f.id !== id));

  const syncDrive = async () => {
    if (picked.length === 0) return toast.error("Pick at least one file");
    setSyncingDrive(true);
    try {
      const { data } = await api.post("/sync/drive", { files: picked });
      toast.success(`Drive: ${data.files_synced} file(s), ${data.chunks_added} chunks`);
      setPicked([]);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Drive sync failed");
    } finally { setSyncingDrive(false); }
  };

  return (
    <div className="max-w-4xl mx-auto px-8 py-10 space-y-8">
      <div>
        <h1 className="font-heading text-4xl" data-testid="sync-title">Sync sources</h1>
        <p className="text-sm text-[#1a1a1a]/70 mt-2">
          Pull data from Google Calendar and Google Drive so the agent can reason about it.
        </p>
      </div>

      {/* Calendar */}
      <section className="bg-white/50 border border-[#1a1a1a]/10 p-6 flex items-start justify-between" data-testid="sync-calendar-card">
        <div className="flex gap-4">
          <div className="w-10 h-10 border border-[#1a1a1a]/20 flex items-center justify-center">
            <Calendar className="w-5 h-5" strokeWidth={1.5} />
          </div>
          <div>
            <h3 className="text-base font-semibold">Google Calendar</h3>
            <p className="text-sm text-[#1a1a1a]/70 mt-1">Ingest upcoming and recent events.</p>
          </div>
        </div>
        <button
          onClick={syncCalendar}
          disabled={syncingCal}
          data-testid="sync-calendar-button"
          className="px-4 py-2 text-sm text-[#f5f1e8] bg-[#1a1a1a] hover:bg-[#b8541f] disabled:opacity-40 transition-colors"
        >
          {syncingCal ? "Syncing…" : "Sync now"}
        </button>
      </section>

      {/* Drive */}
      <section className="bg-white/50 border border-[#1a1a1a]/10 p-6" data-testid="sync-drive-card">
        <div className="flex items-start justify-between mb-4">
          <div className="flex gap-4">
            <div className="w-10 h-10 border border-[#1a1a1a]/20 flex items-center justify-center">
              <HardDrive className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-base font-semibold">Google Drive files</h3>
              <p className="text-sm text-[#1a1a1a]/70 mt-1">Pick files directly from your Drive.</p>
            </div>
          </div>
          <button
            onClick={openPicker}
            data-testid="sync-drive-open-picker"
            className="px-4 py-2 text-sm border border-[#1a1a1a]/20 hover:border-[#1a1a1a] transition-colors"
          >
            Open Drive picker
          </button>
        </div>

        {picked.length > 0 && (
          <ul className="mt-4 divide-y divide-[#1a1a1a]/10 border border-[#1a1a1a]/10">
            {picked.map((f) => (
              <li key={f.id} className="flex items-center justify-between px-4 py-2" data-testid={`sync-drive-picked-${f.id}`}>
                <div className="min-w-0">
                  <p className="text-sm truncate">{f.name}</p>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-[#1a1a1a]/50">{f.mimeType}</p>
                </div>
                <button onClick={() => removePicked(f.id)} className="p-1 text-[#1a1a1a]/50 hover:text-red-600">
                  <X className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-4">
          <button
            onClick={syncDrive}
            disabled={syncingDrive || picked.length === 0}
            data-testid="sync-drive-button"
            className="px-4 py-2 text-sm text-[#f5f1e8] bg-[#1a1a1a] hover:bg-[#b8541f] disabled:opacity-40 transition-colors"
          >
            {syncingDrive ? "Syncing…" : `Sync ${picked.length || ""} file${picked.length === 1 ? "" : "s"}`}
          </button>
        </div>
      </section>
    </div>
  );
}