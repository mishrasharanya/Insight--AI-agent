import { useState } from "react";
import { Calendar, FileUp, HardDrive, X } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";
import { useAuth } from "../lib/useAuth";

export default function Sync() {
  const { user } = useAuth();
  const isGuest = user?.isGuest;
  const [syncingCal, setSyncingCal] = useState(false);
  const [syncingDrive, setSyncingDrive] = useState(false);
  const [syncingFiles, setSyncingFiles] = useState(false);
  const [picked, setPicked] = useState([]);
  const [localFiles, setLocalFiles] = useState([]);
  const [uploadResult, setUploadResult] = useState(null);

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

  const chooseLocalFiles = (event) => {
    setLocalFiles(Array.from(event.target.files || []));
    setUploadResult(null);
  };

  const removeLocalFile = (index) => {
    setLocalFiles((files) => files.filter((_, i) => i !== index));
  };

  const syncLocalFiles = async () => {
    if (localFiles.length === 0) return toast.error("Choose at least one file");

    const formData = new FormData();
    localFiles.forEach((file) => formData.append("files", file));

    setSyncingFiles(true);
    try {
      const { data } = await api.post("/sync/files", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setUploadResult(data);
      if (data.files_synced > 0) {
        toast.success(`Uploaded ${data.files_synced} file(s), ${data.chunks_added} chunks`);
      } else {
        toast.error((data.files || [])[0]?.error || "No chunks were created");
      }
      setLocalFiles([]);
    } catch (err) {
      const detail = err?.response?.status === 404
        ? "Local file upload route not found. Restart the FastAPI backend on port 8000 or deploy the latest API."
        : err?.response?.data?.detail || "File upload failed";
      toast.error(detail);
    } finally { setSyncingFiles(false); }
  };

  return (
    <div className="max-w-4xl mx-auto px-8 py-10 space-y-8">
      <div>
        <h1 className="font-heading text-4xl" data-testid="sync-title">Sync sources</h1>
        <p className="text-sm text-[#1a1a1a]/70 mt-2">
          {isGuest
            ? "Add local files directly. You can connect Google Drive later."
            : "Pull data from Google Calendar, Google Drive, or local files so the agent can reason about it."}
        </p>
      </div>

      {!isGuest && (
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
      )}

      <div className={`grid ${isGuest ? "lg:grid-cols-1" : "lg:grid-cols-2"} gap-6 items-start`}>
        {/* Drive */}
        {!isGuest && <section className="bg-white/50 border border-[#1a1a1a]/10 p-6" data-testid="sync-drive-card">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex gap-4">
              <div className="w-10 h-10 border border-[#1a1a1a]/20 flex items-center justify-center shrink-0">
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
              className="px-4 py-2 text-sm border border-[#1a1a1a]/20 hover:border-[#1a1a1a] transition-colors whitespace-nowrap"
            >
              Open picker
            </button>
          </div>

          {picked.length > 0 && (
            <ul className="mt-4 divide-y divide-[#1a1a1a]/10 border border-[#1a1a1a]/10">
              {picked.map((f) => (
                <li key={f.id} className="flex items-center justify-between gap-3 px-4 py-2" data-testid={`sync-drive-picked-${f.id}`}>
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
        </section>}

        {/* Direct upload */}
        <section className="bg-white/50 border border-[#1a1a1a]/10 p-6" data-testid="sync-local-card">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex gap-4">
              <div className="w-10 h-10 border border-[#1a1a1a]/20 flex items-center justify-center shrink-0">
                <FileUp className="w-5 h-5" strokeWidth={1.5} />
              </div>
              <div>
                <h3 className="text-base font-semibold">Try it yourself</h3>
                <p className="text-sm text-[#1a1a1a]/70 mt-1">Add files directly and get chunks.</p>
              </div>
            </div>
            <label
              data-testid="sync-local-open-picker"
              className="px-4 py-2 text-sm border border-[#1a1a1a]/20 hover:border-[#1a1a1a] transition-colors whitespace-nowrap cursor-pointer"
            >
              Add files
              <input
                type="file"
                multiple
                onChange={chooseLocalFiles}
                className="hidden"
                accept=".txt,.md,.csv,.pdf,.docx,.pptx,.xlsx,.json"
              />
            </label>
          </div>

          {localFiles.length > 0 && (
            <ul className="mt-4 divide-y divide-[#1a1a1a]/10 border border-[#1a1a1a]/10">
              {localFiles.map((file, index) => (
                <li key={`${file.name}-${index}`} className="flex items-center justify-between gap-3 px-4 py-2" data-testid={`sync-local-picked-${index}`}>
                  <div className="min-w-0">
                    <p className="text-sm truncate">{file.name}</p>
                    <p className="font-mono text-[10px] uppercase tracking-widest text-[#1a1a1a]/50">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <button onClick={() => removeLocalFile(index)} className="p-1 text-[#1a1a1a]/50 hover:text-red-600">
                    <X className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          {uploadResult?.files?.length > 0 && (
            <ul className="mt-4 divide-y divide-[#1a1a1a]/10 border border-[#1a1a1a]/10" data-testid="sync-local-result">
              {uploadResult.files.map((file, index) => (
                <li key={`${file.filename}-${index}`} className="grid grid-cols-[1fr_100px] gap-3 px-4 py-2">
                  <span className="text-sm truncate">{file.filename}</span>
                  <span className={`font-mono text-xs text-right ${file.error ? "text-red-600" : "text-[#b8541f]"}`}>
                    {file.error ? "skipped" : `${file.chunks_added} chunks`}
                  </span>
                  {file.error && (
                    <span className="col-span-2 text-xs text-red-600 leading-relaxed">{file.error}</span>
                  )}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4">
            <button
              onClick={syncLocalFiles}
              disabled={syncingFiles || localFiles.length === 0}
              data-testid="sync-local-button"
              className="px-4 py-2 text-sm text-[#f5f1e8] bg-[#1a1a1a] hover:bg-[#b8541f] disabled:opacity-40 transition-colors"
            >
              {syncingFiles ? "Uploading…" : `Get chunks${localFiles.length ? ` for ${localFiles.length}` : ""}`}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
