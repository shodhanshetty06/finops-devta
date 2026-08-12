"use client";

import { Bot, Send, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { answerAssistantQuery } from "@/lib/assistant-knowledge";
import { cn } from "@/lib/utils";
import { useEscapeKey } from "@/hooks/use-dismiss";

interface Message {
  id: string;
  role: "assistant" | "user";
  text: string;
}

const SUGGESTIONS = ["How do discounts work?", "What do validation severities mean?", "What's normalization?", "What optimization features exist?"];

const WELCOME: Message = {
  id: "welcome",
  role: "assistant",
  text: "Hi, I'm the FinOps Assistant. Ask me about pricing, validation, normalization, architecture, or optimization - I answer from this platform's own rules, not a generic model.",
};

/** Floating help widget, bottom-right, mounted once in the app shell. See
 * lib/assistant-knowledge.ts for why this is a local FAQ matcher rather
 * than a live LLM call. */
export function AiAssistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEscapeKey(open, () => setOpen(false));

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open]);

  function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", text: trimmed };
    const { text: answer } = answerAssistantQuery(trimmed);
    const assistantMessage: Message = { id: crypto.randomUUID(), role: "assistant", text: answer };
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setDraft("");
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
                <span className="text-[11px] text-muted-foreground">Answers from platform docs</span>
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
          </div>

          {messages.length <= 1 && (
            <div className="flex flex-wrap gap-1.5 px-4 pb-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-border-strong px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary-300 hover:text-foreground"
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
              className="h-9 w-full rounded-md border border-border-strong bg-input px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button type="submit" size="icon" aria-label="Send" disabled={!draft.trim()}>
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
