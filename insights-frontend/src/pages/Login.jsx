import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, FileSearch, FileUp, Sparkles } from "lucide-react";
import { useAuth } from "../lib/useAuth";

export default function Login() {
  const { user, loading, login, startTrial } = useAuth();
  const navigate = useNavigate();

  const tryBeforeDrive = () => {
    startTrial();
    navigate("/app/chat");
  };

  useEffect(() => {
    if (!loading && user && !user.isGuest) navigate("/app/chat", { replace: true });
  }, [user, loading, navigate]);

  return (
    <div className="min-h-screen bg-[#f5f1e8] text-[#1a1a1a] flex flex-col">
      {/* Header */}
      <header className="border-b border-[#1a1a1a]/10">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-[#b8541f] rounded-full" />
            <span className="font-mono text-xs uppercase tracking-[0.2em]">InsightAI</span>
          </div>
          <button
            onClick={() => login()}
            data-testid="login-header-signin"
            className="font-mono text-xs uppercase tracking-[0.15em] hover:text-[#b8541f] transition-colors"
          >
            Connect Drive ↗
          </button>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-[#1a1a1a]/50 mb-6">
            AI agent for your Google Workspace
          </p>
          <h1 className="font-heading text-5xl sm:text-6xl lg:text-7xl leading-[1] tracking-tight">
            Know your data.
            <br />
            <em className="text-[#b8541f]">Ask, don't search.</em>
          </h1>
          <p className="mt-8 text-base leading-relaxed text-[#1a1a1a]/70 max-w-xl mx-auto">
            InsightAI reads your Google Drive files and Calendar and turns them into a
            searchable brain. Ask questions in plain English — answers grounded in your
            own documents, spreadsheets, and meetings.
          </p>

          <div className="mt-10 flex justify-center gap-3">
            <button
              onClick={() => login()}
              data-testid="login-google-button"
              className="group inline-flex items-center gap-2 px-5 py-3 text-sm font-medium text-[#f5f1e8] bg-[#1a1a1a] hover:bg-[#b8541f] transition-colors"
            >
              Connect Google Drive
              <ArrowUpRight className="w-4 h-4 group-hover:rotate-45 transition-transform" />
            </button>
            <button
              onClick={tryBeforeDrive}
              data-testid="login-try-button"
              className="inline-flex items-center gap-2 px-5 py-3 text-sm font-medium border border-[#1a1a1a]/20 hover:border-[#1a1a1a] transition-colors"
            >
              Want to try it before connecting to Drive?
              <FileUp className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#1a1a1a]/50 mt-5">
            Read-only. Never trains a public model.
          </p>
        </section>

        {/* Example prompts */}
        <section className="max-w-5xl mx-auto px-6 pb-20" data-testid="login-examples">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-[#1a1a1a]/50 mb-6 text-center">
            Ask things like
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {EXAMPLES.map((ex, i) => (
              <div
                key={i}
                data-testid={`login-example-${i}`}
                className="bg-white/50 border border-[#1a1a1a]/10 p-5 hover:border-[#b8541f] hover:-translate-y-0.5 transition-all"
              >
                <p className="font-heading text-lg italic leading-snug">“{ex.q}”</p>
                <p className="font-mono text-[10px] uppercase tracking-widest text-[#1a1a1a]/50 mt-3">
                  → {ex.source}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="border-y border-[#1a1a1a]/10 bg-white/30 py-20">
          <div className="max-w-5xl mx-auto px-6">
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-[#1a1a1a]/50 mb-3 text-center">
              How it works
            </p>
            <h2 className="font-heading text-3xl sm:text-4xl text-center mb-14">
              Three steps. No spreadsheets required.
            </h2>
            <div className="grid md:grid-cols-3 gap-10">
              {STEPS.map((s, i) => (
                <div key={i}>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 border border-[#1a1a1a]/20 flex items-center justify-center">
                      {s.icon}
                    </div>
                    <span className="font-mono text-xs text-[#b8541f]">0{i + 1}</span>
                  </div>
                  <h3 className="font-heading text-2xl mb-2">{s.title}</h3>
                  <p className="text-sm text-[#1a1a1a]/70 leading-relaxed">{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="max-w-2xl mx-auto px-6 py-24 text-center">
          <h2 className="font-heading text-4xl sm:text-5xl">
            Ready to <em className="text-[#b8541f]">talk to your data?</em>
          </h2>
          <p className="mt-4 text-base text-[#1a1a1a]/70">
            Upload a local file first, then connect Drive when you are ready.
          </p>
          <button
            onClick={tryBeforeDrive}
            data-testid="login-cta-button"
            className="group mt-8 inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-[#f5f1e8] bg-[#1a1a1a] hover:bg-[#b8541f] transition-colors"
          >
            Try with local files
            <FileUp className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </section>
      </main>

      <footer className="border-t border-[#1a1a1a]/10">
        <div className="max-w-5xl mx-auto px-6 py-5 flex justify-between font-mono text-xs uppercase tracking-widest text-[#1a1a1a]/50">
          <span>© InsightAI</span>
          <span>Grounded in your workspace</span>
        </div>
      </footer>
    </div>
  );
}

const EXAMPLES = [
  { q: "What did we decide about the Q1 launch last week?", source: "Calendar + Drive" },
  { q: "Summarize the vendor contract I signed with Acme.", source: "PDFs in Drive" },
  { q: "Top 3 regions by revenue in the Q3 forecast?", source: "Google Sheets" },
  { q: "Who am I meeting tomorrow and what's the context?", source: "Calendar + Drive" },
  { q: "Find open action items assigned to me.", source: "Meeting docs" },
  { q: "What did the design review say about typography?", source: "Google Docs" },
];

const STEPS = [
  { title: "Try", icon: <FileUp className="w-5 h-5" strokeWidth={1.5} />, text: "Open chat and add a local file before connecting Drive." },
  { title: "Pick data", icon: <FileSearch className="w-5 h-5" strokeWidth={1.5} />, text: "Upload files directly or choose Drive files later. Indexed privately." },
  { title: "Ask", icon: <Sparkles className="w-5 h-5" strokeWidth={1.5} />, text: "Chat in plain English. Every answer cites the file or meeting it came from." },
];
