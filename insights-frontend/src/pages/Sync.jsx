import { useEffect, useState } from "react";
import { RefreshCw, Calendar, HardDrive, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";
import { useAuth } from "../lib/useAuth";

export default function Sync() {
  const { reconnect } = useAuth();
  const [scopes, setScopes] = useState({ has_drive: false, has_calendar: false });
  const [loadingScopes, setLoadingScopes] = useState(true);
  const [syncingCal, setSyncingCal] = useState(false);
  const [syncingDrive, setSyncingDrive] = useState(false);

  useEffect(() => {
    api.get("/auth/scopes")
      .then(({ data }) => setScopes(data))
      .catch(() => {})
      .finally(() => setLoadingScopes(false));
  }, []);

  const syncCalendar = async () => {
    setSyncingCal(true);
    try {
      const { data } = await api.post("/sync/calendar");
      toast.success(`Synced ${data.count || "your"} calendar events`);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 403) {
        toast.error("Calendar permission not granted. Click Reconnect Google.");
      } else {
        toast.error(err?.response?.data?.detail || "Calendar sync failed");
      }
    } finally {
      setSyncingCal(false);
    }
  };

  const openDrivePicker = async () => {
    setSyncingDrive(true);
    try {
      const { data } = await api.get("/auth/google/picker-token");
      toast.success("Picker token ready — implement Google Picker UI here");
      console.log("Picker config:", data);
      // TODO: wire up Google Picker API with data.access_token, data.developer_key, etc.
    } catch (err) {
      const status = err?.response?.status;
      if (status === 403) {
        toast.error("Drive permission not granted. Click Reconnect Google.");
      } else {
        toast.error(err?.response?.data?.detail || "Drive picker failed");
      }
    } finally {
      setSyncingDrive(false);
    }
  };

  return (
    <div className="px-8 py-8 max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="font-heading text-3xl" data-testid="sync-title">Sync your data</h1>
        <p className="text-sm text-[#1a1a1a]/70 mt-1">
          Pick Google Drive files and sync your Calendar to make them searchable.
        </p>
      </div>

      {/* Reconnect banner if any scope is missing */}
      {!loadingScopes && (!scopes.has_drive || !scopes.has_calendar) && (
        <div className="border border-[#b8541f]/30 bg-[#b8541f]/5 p-5" data-testid="reconnect-banner">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-[#b8541f] shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-[#1a1a1a] text-sm">Some permissions are missing</h3>
              <p className="text-sm text-[#1a1a1a]/70 mt-1">
                To use all features, reconnect Google and grant the permissions you skipped.
              </p>
              <button
                onClick={reconnect}
                data-testid="reconnect-google-button"
                className="mt-3 inline-flex items-center gap-2 text-sm text-[#f5f1e8] bg-[#1a1a1a] hover:bg-[#b8541f] px-4 py-2 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Reconnect Google
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Drive card */}
      <div className="border border-[#1a1a1a]/10 p-6 bg-white/50" data-testid="sync-drive-card">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 bg-[#1a1a1a] text-[#f5f1e8] flex items-center justify-center shrink-0">
            <HardDrive className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h2 className="font-heading text-xl">Google Drive</h2>
              {scopes.has_drive && <CheckCircle2 className="w-4 h-4 text-[#5B96A8]" />}
            </div>
            <p className="text-sm text-[#1a1a1a]/70 mt-1">
              Pick individual files to index. Read-only access, only the files you choose.
            </p>
            <button
              onClick={openDrivePicker}
              disabled={!scopes.has_drive || syncingDrive}
              data-testid="pick-drive-files-button"
              className="mt-4 inline-flex items-center gap-2 text-sm text-[#1a1a1a] bg-white border border-[#1a1a1a]/20 hover:border-[#b8541f] disabled:opacity-40 disabled:cursor-not-allowed px-4 py-2 transition-colors"
            >
              {syncingDrive ? "Loading…" : "Pick files"}
            </button>
          </div>
        </div>
      </div>

      {/* Calendar card */}
      <div className="border border-[#1a1a1a]/10 p-6 bg-white/50" data-testid="sync-calendar-card">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 bg-[#1a1a1a] text-[#f5f1e8] flex items-center justify-center shrink-0">
            <Calendar className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h2 className="font-heading text-xl">Google Calendar</h2>
              {scopes.has_calendar && <CheckCircle2 className="w-4 h-4 text-[#5B96A8]" />}
            </div>
            <p className="text-sm text-[#1a1a1a]/70 mt-1">
              Sync your calendar events so you can ask about meetings, decisions, and action items.
            </p>
            <button
              onClick={syncCalendar}
              disabled={!scopes.has_calendar || syncingCal}
              data-testid="sync-calendar-button"
              className="mt-4 inline-flex items-center gap-2 text-sm text-[#1a1a1a] bg-white border border-[#1a1a1a]/20 hover:border-[#b8541f] disabled:opacity-40 disabled:cursor-not-allowed px-4 py-2 transition-colors"
            >
              {syncingCal ? "Syncing…" : "Sync calendar"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}