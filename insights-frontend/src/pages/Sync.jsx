import { useState } from "react";
import { Calendar, HardDrive } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";

export default function Sync() {
  const [syncingCal, setSyncingCal] = useState(false);
  const [syncingDrive, setSyncingDrive] = useState(false);

  const syncCalendar = async () => {
    setSyncingCal(true);
    try {
      const { data } = await api.post("/sync/calendar");
      toast.success(`Synced ${data.count || "your"} calendar events`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Calendar sync failed");
    } finally {
      setSyncingCal(false);
    }
  };

  const openDrivePicker = async () => {
    setSyncingDrive(true);
    try {
      const { data } = await api.get("/auth/google/picker-token");
      toast.success("Picker token ready");
      console.log("Picker config:", data);
      // TODO: wire your Google Picker JS SDK here
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Drive picker failed");
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

      <div className="border border-[#1a1a1a]/10 p-6 bg-white/50">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 bg-[#1a1a1a] text-[#f5f1e8] flex items-center justify-center shrink-0">
            <HardDrive className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h2 className="font-heading text-xl">Google Drive</h2>
            <p className="text-sm text-[#1a1a1a]/70 mt-1">
              Pick individual files to index. Read-only access, only the files you choose.
            </p>
            <button
              onClick={openDrivePicker}
              disabled={syncingDrive}
              data-testid="pick-drive-files-button"
              className="mt-4 inline-flex items-center gap-2 text-sm text-[#1a1a1a] bg-white border border-[#1a1a1a]/20 hover:border-[#b8541f] disabled:opacity-40 px-4 py-2 transition-colors"
            >
              {syncingDrive ? "Loading…" : "Pick files"}
            </button>
          </div>
        </div>
      </div>

      <div className="border border-[#1a1a1a]/10 p-6 bg-white/50">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 bg-[#1a1a1a] text-[#f5f1e8] flex items-center justify-center shrink-0">
            <Calendar className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h2 className="font-heading text-xl">Google Calendar</h2>
            <p className="text-sm text-[#1a1a1a]/70 mt-1">
              Sync your calendar events so you can ask about meetings, decisions, and action items.
            </p>
            <button
              onClick={syncCalendar}
              disabled={syncingCal}
              data-testid="sync-calendar-button"
              className="mt-4 inline-flex items-center gap-2 text-sm text-[#1a1a1a] bg-white border border-[#1a1a1a]/20 hover:border-[#b8541f] disabled:opacity-40 px-4 py-2 transition-colors"
            >
              {syncingCal ? "Syncing…" : "Sync calendar"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}