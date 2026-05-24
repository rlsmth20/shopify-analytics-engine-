"use client";

import Link from "next/link";
import { FormEvent, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth-guard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type ChatRole = "user" | "assistant";

type ChatMessage = {
  role: ChatRole;
  content: string;
};

type RelatedLink = {
  label: string;
  href: string;
};

type ChatResponse = {
  answer: string;
  mode: "ai" | "local";
  data_source: "db" | "mock";
  context_summary: string;
  related_links: RelatedLink[];
};

const STARTER_PROMPTS = [
  "What should I reorder this week?",
  "Which SKUs are tying up cash?",
  "What stockout risks need attention?",
  "Which supplier lead times look risky?"
];

const WELCOME_MESSAGE: ChatMessage = {
  role: "assistant",
  content:
    "Ask me about reorder priorities, stockout risk, dead stock, suppliers, bundles, or why an item is ranked in your action queue."
};

export function AskSkubaseChat() {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [relatedLinks, setRelatedLinks] = useState<RelatedLink[]>([]);
  const [contextSummary, setContextSummary] = useState("");
  const [mode, setMode] = useState<ChatResponse["mode"] | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const visibleMessages = useMemo(
    () => messages.filter((message) => message.content.trim()),
    [messages]
  );

  function openChat() {
    setIsOpen(true);
    window.setTimeout(() => inputRef.current?.focus(), 50);
  }

  async function submitQuestion(question: string) {
    const trimmed = question.trim();
    if (!trimmed || isSending) return;

    setError("");
    setInput("");
    const nextMessages = [...messages, { role: "user" as const, content: trimmed }];
    setMessages(nextMessages);

    if (user.id === 0) {
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content:
            "Demo mode uses sample inventory data. Sign up or connect Shopify to ask about your own SKU actions, stockout risks, dead stock, and supplier lead times."
        }
      ]);
      setRelatedLinks([{ label: "Start free trial", href: "/login" }]);
      return;
    }

    setIsSending(true);
    try {
      const response = await fetch(`${API_BASE}/ai/chat`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify({
          messages: nextMessages.slice(-10)
        })
      });

      if (!response.ok) {
        throw new Error(`Ask Skubase failed with status ${response.status}.`);
      }

      const data = (await response.json()) as ChatResponse;
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: data.answer
        }
      ]);
      setRelatedLinks(data.related_links);
      setContextSummary(data.context_summary);
      setMode(data.mode);
    } catch {
      setError("Ask Skubase could not answer right now. Try again in a moment.");
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content:
            "I could not reach the inventory assistant just now. Your action queue and forecast pages still have the latest ranked recommendations."
        }
      ]);
      setRelatedLinks([{ label: "Open action queue", href: "/actions" }]);
    } finally {
      setIsSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuestion(input);
  }

  return (
    <div className={`ask-skubase${isOpen ? " ask-skubase-open" : ""}`}>
      {isOpen ? (
        <section className="ask-panel" aria-label="Ask Skubase inventory chat">
          <div className="ask-panel-header">
            <div>
              <p className="ask-eyebrow">Inventory copilot</p>
              <h2 className="ask-title">Ask Skubase</h2>
            </div>
            <button
              type="button"
              className="ask-icon-button"
              aria-label="Close Ask Skubase"
              onClick={() => setIsOpen(false)}
            >
              x
            </button>
          </div>

          <div className="ask-thread" aria-live="polite">
            {visibleMessages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`ask-message ask-message-${message.role}`}
              >
                <span className="ask-message-label">
                  {message.role === "user" ? "You" : "Skubase"}
                </span>
                <p>{message.content}</p>
              </div>
            ))}
            {isSending ? (
              <div className="ask-message ask-message-assistant">
                <span className="ask-message-label">Skubase</span>
                <p>Reading your current action queue...</p>
              </div>
            ) : null}
          </div>

          {messages.length === 1 ? (
            <div className="ask-prompts" aria-label="Suggested questions">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="ask-prompt"
                  onClick={() => void submitQuestion(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          ) : null}

          {relatedLinks.length > 0 ? (
            <div className="ask-links">
              {relatedLinks.map((link) => (
                <Link key={`${link.href}-${link.label}`} href={link.href}>
                  {link.label}
                </Link>
              ))}
            </div>
          ) : null}

          {contextSummary || mode ? (
            <p className="ask-footnote">
              {contextSummary ? contextSummary : "Read-only inventory guidance"}
              {mode === "local" ? " - local fallback" : ""}
            </p>
          ) : (
            <p className="ask-footnote">Read-only. Ask Skubase will not change Shopify inventory.</p>
          )}
          {error ? <p className="ask-error" role="alert">{error}</p> : null}

          <form className="ask-form" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="ask-skubase-input">
              Ask an inventory question
            </label>
            <textarea
              id="ask-skubase-input"
              ref={inputRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask what to reorder, clear, or review..."
              rows={2}
              maxLength={1000}
            />
            <button type="submit" className="ask-send" disabled={isSending || !input.trim()}>
              Send
            </button>
          </form>
        </section>
      ) : null}

      <button
        type="button"
        className="ask-launcher"
        aria-expanded={isOpen}
        aria-controls="ask-skubase-input"
        onClick={openChat}
      >
        Ask Skubase
      </button>
    </div>
  );
}
