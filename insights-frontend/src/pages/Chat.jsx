import { useState, useRef, useEffect } from "react";
import { Send, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import api from "../lib/api";

const CHAT_STORAGE_KEY = "insight_chat";

export default function Chat() {
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem(CHAT_STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);

  // Persist chat to localStorage on every change
  useEffect(() => {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const clearChat = () => {
    setMessages([]);
    localStorage.removeItem(CHAT_STORAGE_KEY);
    toast.success("Chat cleared");
  };

  const send = async (e) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || sending) return;

    setMessages((m) => [...m, { role: "user", text: q }]);
    setQuestion("");
    setSending(true);

    try {
      const { data } = await api.post("/chat", { question: q });
      setMessages((m) => [...m, {
        role: "assistant",
        text: data.answer || "No answer.",
        route: data.route,
        tier: data.confidence_tier,
      }]);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Chat failed";
      toast.error(String(detail));
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${detail}`, isError: true }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="border-b border-[#1a1a1a]/10 px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="font-heading text-3xl" data-testid="chat-title">Ask InsightAI</h1>
          <p className="text-sm text-[#1a1a1a]/70 mt-1">
            Chat with an agent that reads your synced Drive files and Calendar.
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            data-testid="chat-clear-button"
            className="flex items-center gap-2 text-xs uppercase tracking-widest text-[#1a1a1a]/50 hover:text-[#b8541f] transition-colors font-mono"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear chat
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-8" data-testid="chat-messages">
        <div className="max-w-3xl mx-auto space-y-8">
          {messages.length === 0 && <EmptyState onPrompt={setQuestion} />}
          {messages.map((m, i) => <Message key={i} message={m} />)}
          {sending && (
            <div className="flex gap-4" data-testid="chat-thinking">
              <div className="w-8 h-8 bg-[#1a1a1a] text-[#f5f1e8] flex items-center justify-center shrink-0">
                <Sparkles className="w-4 h-4" />
              </div>
              <div className="pt-1.5 text-sm text-[#1a1a1a]/60 animate-pulse">Thinking…</div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="border-t border-[#1a1a1a]/10 px-8 py-5">
        <form onSubmit={send} className="max-w-3xl mx-auto relative">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your data…"
            data-testid="chat-input"
            className="block w-full px-5 py-3.5 bg-white/50 border border-[#1a1a1a]/20 placeholder-[#1a1a1a]/40 focus:outline-none focus:border-[#b8541f] text-base pr-14 transition-colors"
          />
          <button
            type="submit"
            disabled={sending || !question.trim()}
            data-testid="chat-send-button"
            className="absolute right-1.5 top-1/2 -translate-y-1/2 w-11 h-11 bg-[#1a1a1a] text-[#f5f1e8] flex items-center justify-center disabled:opacity-40 hover:bg-[#b8541f] transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}

const markdownComponents = {
  h1: ({ node, children, ...props }) => <h1 className="font-heading text-xl mt-4 mb-2 text-[#1a1a1a]" {...props}>{children}</h1>,
  h2: ({ node, children, ...props }) => <h2 className="font-heading text-lg mt-4 mb-2 text-[#1a1a1a]" {...props}>{children}</h2>,
  h3: ({ node, children, ...props }) => <h3 className="font-heading text-base mt-4 mb-1.5 text-[#1a1a1a] uppercase tracking-wide" {...props}>{children}</h3>,
  p: ({ node, children, ...props }) => <p className="text-sm leading-relaxed my-2 text-[#1a1a1a]" {...props}>{children}</p>,
  strong: ({ node, children, ...props }) => <strong className="font-semibold text-[#1a1a1a]" {...props}>{children}</strong>,
  em: ({ node, children, ...props }) => <em className="italic text-[#1a1a1a]/80" {...props}>{children}</em>,
  ul: ({ node, children, ...props }) => <ul className="list-disc pl-5 my-2 space-y-1 text-sm text-[#1a1a1a]" {...props}>{children}</ul>,
  ol: ({ node, children, ...props }) => <ol className="list-decimal pl-5 my-2 space-y-1 text-sm text-[#1a1a1a]" {...props}>{children}</ol>,
  li: ({ node, children, ...props }) => <li className="leading-relaxed" {...props}>{children}</li>,
  code: ({ node, inline, children, ...props }) =>
    inline
      ? <code className="px-1.5 py-0.5 bg-[#1a1a1a]/5 text-[#b8541f] font-mono text-[13px] rounded-sm" {...props}>{children}</code>
      : <code className="block p-3 bg-[#1a1a1a]/5 text-[#1a1a1a] font-mono text-[13px] rounded-sm overflow-x-auto my-2" {...props}>{children}</code>,
  pre: ({ node, children, ...props }) => <pre className="my-2" {...props}>{children}</pre>,
  blockquote: ({ node, children, ...props }) => <blockquote className="border-l-2 border-[#b8541f] pl-4 my-2 italic text-[#1a1a1a]/80 text-sm" {...props}>{children}</blockquote>,
  a: ({ node, children, ...props }) => <a className="text-[#b8541f] underline underline-offset-2 hover:text-[#1a1a1a] transition-colors" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>,
  table: ({ node, children, ...props }) => <div className="overflow-x-auto my-3"><table className="w-full text-sm border-collapse" {...props}>{children}</table></div>,
  thead: ({ node, children, ...props }) => <thead className="border-b border-[#1a1a1a]/20" {...props}>{children}</thead>,
  th: ({ node, children, ...props }) => <th className="text-left px-3 py-2 font-semibold text-[#1a1a1a] text-xs uppercase tracking-wide" {...props}>{children}</th>,
  td: ({ node, children, ...props }) => <td className="px-3 py-2 border-b border-[#1a1a1a]/10 text-[#1a1a1a]" {...props}>{children}</td>,
  hr: ({ node, ...props }) => <hr className="my-4 border-[#1a1a1a]/10" {...props} />,
};

function Message({ message }) {
  const isUser = message.role === "user";
  return (
    <div className="flex gap-4" data-testid={`chat-message-${message.role}`}>
      <div className={`w-8 h-8 flex items-center justify-center text-xs font-mono shrink-0 ${isUser ? "bg-[#1a1a1a]/10 text-[#1a1a1a]" : "bg-[#1a1a1a] text-[#f5f1e8]"}`}>
        {isUser ? "YOU" : <Sparkles className="w-4 h-4" />}
      </div>
      <div className={`pt-1 flex-1 min-w-0 ${message.isError ? "text-red-600" : "text-[#1a1a1a]"}`}>
        {isUser || message.isError ? (
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.text}</p>
        ) : (
          <div className="markdown-body" data-testid="chat-message-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message.text}</ReactMarkdown>
          </div>
        )}
        {!isUser && message.tier && (
          <div className="mt-3 flex items-center gap-3">
            <ConfidenceMeter tier={message.tier} />
            {message.route && (
              <span className="font-mono text-[10px] uppercase tracking-widest text-[#1a1a1a]/50">route: {message.route}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ConfidenceMeter({ tier }) {
  const filled = { high: 3, medium: 2, low: 1 }[tier] || 0;
  const color = { high: "#5B96A8", medium: "#C98A3B", low: "#B25050" }[tier] || "#ccc";
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <div key={i} className="w-4 h-1 rounded-sm" style={{ background: i < filled ? color : "#1a1a1a20" }} />
        ))}
      </div>
      <span className="font-mono text-[10px] uppercase tracking-widest text-[#1a1a1a]/50">confidence: {tier}</span>
    </div>
  );
}

const SUGGESTIONS = [
  "Summarize my calendar for this week",
  "What files did I sync recently?",
  "Find action items from my last meeting",
];

function EmptyState({ onPrompt }) {
  return (
    <div className="text-center py-16" data-testid="chat-empty-state">
      <div className="inline-flex w-12 h-12 bg-[#1a1a1a] text-[#f5f1e8] items-center justify-center mb-6">
        <Sparkles className="w-5 h-5" />
      </div>
      <h2 className="font-heading text-3xl">How can I help?</h2>
      <p className="text-sm text-[#1a1a1a]/60 mt-2">Try one of these to get started.</p>
      <div className="mt-8 flex flex-col sm:flex-row justify-center gap-2 max-w-2xl mx-auto">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPrompt(s)}
            data-testid={`chat-suggestion-${s.slice(0, 10)}`}
            className="text-left text-sm text-[#1a1a1a] bg-white/50 border border-[#1a1a1a]/10 hover:border-[#b8541f] px-4 py-3 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}