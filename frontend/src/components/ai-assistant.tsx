"use client";

import { Bot, Send, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useAssistantData } from "@/contexts/assistant-context";
import { apiErrorMessage, assistantApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useEscapeKey } from "@/hooks/use-dismiss";

interface Message {
  id: string;
  role: "assistant" | "user";
  text: string;
}

// How many prior turns to resend as context on each call - a support widget
// doesn't need the full transcript, and every turn resent is billed input
// tokens on every subsequent message (see backend/app/domain/assistant.py).
const MAX_HISTORY_TURNS = 10;

const SUGGESTIONS = ["How do discounts work?", "What do validation severities mean?", "What's normalization?", "What optimization features exist?"];

const WELCOME: Message = {
  id: "welcome",
  role: "assistant",
  text: "Hi, I'm the FinOps Assistant, powered by Groq. Ask me about pricing, validation, normalization, architecture, or optimization on this platform - or about the estimate/comparison you currently have open.",
};

/** Floating help widget, bottom-right, mounted once in the app shell. Calls
 * POST /api/v1/assistant/chat (backend/app/api/routers/assistant.py), which
 * itself calls Groq with a system prompt grounded in this platform's real
 * documented behavior - see backend/app/services/assistant_service.py.
 * Also forwards whatever estimate/comparison the current page has registered
 * via frontend/src/contexts/assistant-context.tsx, so questions about actual
 * costs/assumptions/resources get grounded, real answers instead of "I don't
 * have access to live pricing data". */
export function AiAssistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { estimate, comparison } = useAssistantData();

  useEscapeKey(open, () => setOpen(false));

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open, sending]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const history = messages
      .filter((m) => m.id !== "welcome")
      .slice(-MAX_HISTORY_TURNS)
      .map((m) => ({ role: m.role, text: m.text }));

    const userMessage: Message = { id: crypto.randomUUID(), role: "user", text: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setDraft("");
    setSending(true);

    try {
      const { text: answer } = await assistantApi.chat(trimmed, history, { estimate, comparison });
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", text: answer }]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", text: `Sorry, I couldn't get an answer: ${apiErrorMessage(error)}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      {open && (
        <div
          role="dialog"
          aria-modal="false"
          aria-label="FinOps Assistant"
          className="fixed bottom-24 right-4 z-40 flex h-[28rem] w-[22rem] flex-col overflow-hidden rounded-xl border border-border bg-surface-raised shadow-lg animate-slide-up sm:right-6"
        >
          <div className="flex items-center justify-between gap-2 border-b border-border bg-muted/50 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Sparkles className="h-3.5 w-3.5" />
              </span>
              <div className="flex flex-col leading-tight">
                <span className="text-sm font-semibold text-foreground">FinOps Assistant</span>
                <span className="text-[11px] text-muted-foreground">Powered by Groq</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close assistant"
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.map((m) => (
              <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[85%] rounded-lg px-3 py-2 text-[13px] leading-relaxed",
                    m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
                  )}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1 rounded-lg bg-muted px-3 py-2 text-foreground">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current" />
                </div>
              </div>
            )}
          </div>

          {messages.length <= 1 && (
            <div className="flex flex-wrap gap-1.5 px-4 pb-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  disabled={sending}
                  className="rounded-full border border-border-strong px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary-300 hover:text-foreground disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
            className="flex items-center gap-2 border-t border-border p-3"
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about pricing, validation..."
              aria-label="Message the assistant"
              disabled={sending}
              className="h-9 w-full rounded-md border border-border-strong bg-input px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            />
            <Button type="submit" size="icon" aria-label="Send" disabled={!draft.trim() || sending}>
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close FinOps Assistant" : "Open FinOps Assistant"}
        aria-expanded={open}
        className="fixed bottom-5 right-4 z-40 flex h-[3.25rem] w-[3.25rem] items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105 active:scale-95 sm:right-6"
      >
        {open ? <X className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
      </button>
    </>
  );
}
