import type { PartyRole } from "@/lib/api";

export type ConversationDisplayMessage = {
  id: string;
  role: PartyRole;
  roleName: string;
  text: string;
  order: number;
  timestamp?: string | null;
};

export function ConversationGuide() {
  return (
    <aside className="conversation-guide" aria-labelledby="conversation-guide-title">
      <strong id="conversation-guide-title">Discuss the work naturally. Before finishing, try to cover:</strong>
      <ul>
        <li>what work will be done</li>
        <li>the price and selected currency</li>
        <li>whether materials are included</li>
        <li>when work starts and finishes</li>
        <li>when payment is due</li>
        <li>what happens before extra work or extra cost</li>
      </ul>
      <small>These are suggestions, not required fields.</small>
    </aside>
  );
}

export function ChatMessageList({
  messages,
}: {
  messages: ConversationDisplayMessage[];
}) {
  return (
    <div className="chat-thread" aria-live="polite">
      {messages.length ? messages.map((message) => (
        <article className={`chat-bubble ${message.role}`} key={message.id}>
          <span>{message.roleName}</span>
          <p>{message.text}</p>
          <time dateTime={message.timestamp ?? undefined}>
            Message {message.order}
            {message.timestamp
              ? ` · ${new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
              : ""}
          </time>
        </article>
      )) : (
        <div className="chat-empty">
          <strong>No messages yet</strong>
          <p>Start with what work is needed, price, timing, materials, and payment.</p>
        </div>
      )}
    </div>
  );
}
