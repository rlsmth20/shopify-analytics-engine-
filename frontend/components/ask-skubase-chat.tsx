"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth-guard";
import { API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch } from "@/lib/shopify-embedded";
import { CHAT_TIMEOUT_MS, chatErrorCopy, chatFallbackExplanation, chatReplyLabel, chatRequestMessages, chatTextBlocks, parseChatReply, type InventoryChatMessage } from "@/lib/inventory-chat";

const STARTER_PROMPTS = ["What should I reorder this week?", "Which SKUs are tying up cash?", "What stockout risks need attention?", "Which supplier lead times look risky?"];
const WELCOME_MESSAGE: InventoryChatMessage = { id: "welcome", role: "assistant", content: "Ask about reorder priorities, stockout risk, dead stock, suppliers, bundles, or why an item is ranked in your action queue." };

function ReplyText({ text }: { text: string }) {
  const inline = (line: string) => line.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith("**") && part.endsWith("**") ? <strong key={index}>{part.slice(2, -2)}</strong> : part);
  return <>{chatTextBlocks(text).map((block, index) => {
    if (block.kind === "ordered" || block.kind === "unordered") {
      const List = block.kind === "ordered" ? "ol" : "ul";
      return <List key={index} style={{ paddingLeft: 20, margin: "4px 0", display: "grid", gap: 7 }}>{block.lines.map((line, item) => <li key={item}>{inline(line)}</li>)}</List>;
    }
    return <p key={index}>{block.kind === "heading" ? <strong>{inline(block.lines.join("\n"))}</strong> : inline(block.lines.join("\n"))}</p>;
  })}</>;
}

export function AskSkubaseChat() {
  const { user } = useAuth();
  const scope = `${user.shop_id}:${user.id}`;
  const [isOpen, setIsOpen] = useState(false);
  const [session, setSession] = useState<{ scope: string; messages: InventoryChatMessage[] }>({ scope, messages: [WELCOME_MESSAGE] });
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const launcherRef = useRef<HTMLButtonElement | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);
  const activeScope = useRef(scope);
  const sequence = useRef(0);
  const request = useRef<{ scope: string; controller: AbortController; questionId: string } | null>(null);
  activeScope.current = scope;
  const messages = session.scope === scope ? session.messages : [WELCOME_MESSAGE];
  const isSending = messages.some(message => message.status === "sending");
  const failedQuestion = messages[messages.length - 1]?.status === "failed" ? messages[messages.length - 1] : null;

  useEffect(() => {
    activeScope.current = scope;
    request.current?.controller.abort();
    request.current = null;
    setSession({ scope, messages: [WELCOME_MESSAGE] });
    setInput("");
    setIsOpen(false);
    return () => { activeScope.current = ""; request.current?.controller.abort(); request.current = null; };
  }, [scope]);
  useEffect(() => { if (isOpen) inputRef.current?.focus({ preventScroll: true }); }, [isOpen]);
  useEffect(() => { if (isOpen && threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight; }, [isOpen, session]);

  function closeChat() { setIsOpen(false); launcherRef.current?.focus({ preventScroll: true }); }

  async function submitQuestion(question: string, retryId?: string) {
    const trimmed = question.trim().slice(0, 1000);
    if (!trimmed || request.current?.scope === scope || activeScope.current !== scope) return;
    const questionId = retryId || failedQuestion?.id || `question-${++sequence.current}`;
    const nextQuestion: InventoryChatMessage = { id: questionId, role: "user", content: trimmed, status: "sending" };
    const nextMessages = messages.some(message => message.id === questionId)
      ? messages.map(message => message.id === questionId ? nextQuestion : message) : [...messages, nextQuestion];
    setSession({ scope, messages: nextMessages });
    if (!retryId) setInput("");
    if (user.id === 0) {
      setSession({ scope, messages: [...nextMessages.map(message => ({ ...message, status: undefined })), {
        id: `answer-${++sequence.current}`, role: "assistant", sample: true,
        content: "This sample workspace does not send chat questions to a model. Sign in to review your own inventory. Skubase is in Shopify’s review process and is not yet listed in the App Store; existing approved connections can sync, and Store Sync explains the available import options.",
      }] });
      return;
    }
    const controller = new AbortController();
    const current = { scope, controller, questionId };
    request.current = current;
    let failureCopy = chatErrorCopy();
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const operation = (async () => {
        const response = await authenticatedFetch(`${API_BASE_URL}/ai/chat`, {
          method: "POST", credentials: "include", signal: controller.signal,
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ messages: chatRequestMessages(nextMessages) }),
        });
        if (!response.ok) { failureCopy = chatErrorCopy(response.status); throw new Error("Chat request failed"); }
        return parseChatReply(await response.json());
      })();
      const timeout = new Promise<never>((_, reject) => {
        timer = setTimeout(() => { failureCopy = "This reply took too long. Retry your question when you’re ready."; controller.abort(); reject(new Error("Chat timeout")); }, CHAT_TIMEOUT_MS);
      });
      const reply = await Promise.race([operation, timeout]);
      if (activeScope.current !== scope || request.current !== current || controller.signal.aborted) return;
      setSession({ scope, messages: [...nextMessages.map(message => ({ ...message, status: undefined })), { id: `answer-${++sequence.current}`, role: "assistant", content: reply.answer, reply }] });
    } catch {
      if (activeScope.current !== scope || request.current !== current) return;
      setSession({ scope, messages: nextMessages.map(message => message.id === questionId ? { ...message, status: "failed", error: failureCopy } : message) });
    } finally {
      clearTimeout(timer);
      if (request.current === current) request.current = null;
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void submitQuestion(input); }
  return <div className={`ask-skubase${isOpen ? " ask-skubase-open" : ""}`}>
    {isOpen ? <section id="ask-skubase-panel" className="ask-panel" aria-label="Ask Skubase inventory chat" style={{ display: "flex", flexDirection: "column" }}
      onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); closeChat(); } }}>
      <div className="ask-panel-header" style={{ flexShrink: 0 }}><div><p className="ask-eyebrow">Inventory copilot</p><h2 className="ask-title">Ask Skubase</h2></div><button type="button" className="ask-icon-button" aria-label="Close Ask Skubase" onClick={closeChat}>×</button></div>
      <div ref={threadRef} className="ask-thread" role="log" aria-label="Inventory conversation" aria-live="polite" aria-relevant="additions text" aria-busy={isSending} tabIndex={0} style={{ flex: "1 1 auto", minHeight: 80, overflowWrap: "anywhere" }}>
        {messages.map(message => <article key={message.id} className={`ask-message ask-message-${message.role}`} style={{ minWidth: 0 }}>
          <span className="ask-message-label">{message.role === "user" ? "You" : message.sample ? "Sample workspace" : message.reply ? `Skubase · ${chatReplyLabel(message.reply)}` : "Skubase"}</span>
          <ReplyText text={message.content} />
          {message.status === "failed" ? <><p role="alert" style={{ color: "var(--danger, #a42a24)", fontSize: ".82rem" }}>{message.error}</p><div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}><button type="button" className="ask-prompt" onClick={() => void submitQuestion(message.content, message.id)}>Retry question</button><button type="button" className="ask-prompt" onClick={() => { setInput(message.content); inputRef.current?.focus({ preventScroll: true }); }}>Edit question</button></div></> : null}
          {message.reply ? <>
            {chatFallbackExplanation(message.reply) ? <p style={{ fontSize: ".78rem", color: "var(--muted)" }}>{chatFallbackExplanation(message.reply)}</p> : null}
            <p style={{ fontSize: ".75rem", color: "var(--muted)" }}>{message.reply.data_source === "mock" ? "Sample inventory" : "Recorded inventory"}{message.reply.context_summary ? ` · ${message.reply.context_summary}` : ""}</p>
            {message.reply.related_links.length ? <nav className="ask-links" aria-label="Related inventory pages" style={{ padding: 0 }}>{message.reply.related_links.map(link => <Link key={link.href} href={link.href}>{link.label}</Link>)}</nav> : null}
          </> : null}
          {message.sample ? <Link href="/login">Sign in</Link> : null}
        </article>)}
        {isSending ? <p role="status">Checking the available inventory context…</p> : null}
      </div>
      {messages.length === 1 ? <div className="ask-prompts" aria-label="Suggested questions" style={{ flexShrink: 0 }}>{STARTER_PROMPTS.map(prompt => <button key={prompt} type="button" className="ask-prompt" onClick={() => void submitQuestion(prompt)}>{prompt}</button>)}</div> : null}
      <p className="ask-footnote" style={{ flexShrink: 0 }}>Read-only guidance. Replies do not change Shopify inventory.</p>
      <form className="ask-form" onSubmit={handleSubmit} style={{ flexShrink: 0 }}>
        <label className="sr-only" htmlFor="ask-skubase-input">Ask an inventory question</label>
        <textarea id="ask-skubase-input" ref={inputRef} value={session.scope === scope ? input : ""} onChange={event => setInput(event.target.value)} placeholder="Ask what to reorder, clear, or review…" rows={2} maxLength={1000} disabled={isSending} />
        <button type="submit" className="ask-send" disabled={isSending || !input.trim()}>{isSending ? "Waiting…" : "Send"}</button>
      </form>
    </section> : null}
    <button type="button" ref={launcherRef} className="ask-launcher" aria-expanded={isOpen} aria-controls={isOpen ? "ask-skubase-panel" : undefined} onClick={() => setIsOpen(true)}>Ask Skubase</button>
  </div>;
}
