import type { LanguageCode, PartyRole, TranslationStatus } from "@/lib/api";
import { languageName, t } from "@/lib/i18n";

export type ConversationDisplayMessage = {
  id: string;
  role: PartyRole;
  roleName: string;
  text: string;
  order: number;
  timestamp?: string | null;
  inputSource?: "text" | "audio_transcript";
  rawTranscript?: string | null;
  correctedText?: string | null;
  originalLanguage?: LanguageCode;
  translatedText?: string | null;
  translationStatus?: TranslationStatus;
  translationLanguage?: LanguageCode;
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
  preferredLanguage = "en",
  onRetryTranslation,
  showAllTranslations = false,
}: {
  messages: ConversationDisplayMessage[];
  preferredLanguage?: LanguageCode;
  onRetryTranslation?: (messageId: string) => void;
  showAllTranslations?: boolean;
}) {
  return (
    <div className="chat-thread" aria-live="polite">
      {messages.length ? messages.map((message) => (
        <article className={`chat-bubble ${message.role}`} key={message.id}>
          <span>{message.roleName}</span>
          {message.inputSource === "audio_transcript" ? (
            <small className="audio-provenance">Audio transcript{message.correctedText ? " · Corrected after transcription" : ""}</small>
          ) : null}
          {message.originalLanguage && (showAllTranslations || message.originalLanguage !== preferredLanguage) ? (
            <div className="bilingual-message">
              <small>{t(preferredLanguage, "original")} · {languageName(message.originalLanguage)}</small>
              <p lang={message.originalLanguage}>{message.text}</p>
              {message.translationStatus === "ready" && message.translatedText ? (
                <div className="translated-message">
                  <small>{t(preferredLanguage, "translated")} · {languageName(message.translationLanguage ?? preferredLanguage)}</small>
                  <p lang={message.translationLanguage ?? preferredLanguage}>{message.translatedText}</p>
                </div>
              ) : message.translationStatus === "pending" ? (
                <small role="status">{t(preferredLanguage, "translationPending")}</small>
              ) : message.translationStatus === "failed" ? (
                <div className="translation-failure" role="status">
                  <small>{t(preferredLanguage, "translationFailed")}</small>
                  {onRetryTranslation ? <button className="text-action" type="button" onClick={() => onRetryTranslation(message.id)}>{t(preferredLanguage, "retryTranslation")}</button> : null}
                </div>
              ) : null}
            </div>
          ) : (
            <p lang={message.originalLanguage ?? preferredLanguage}>{message.text}</p>
          )}
          {message.inputSource === "audio_transcript" && message.correctedText && message.rawTranscript ? (
            <details className="raw-transcript">
              <summary>See original machine transcript</summary>
              <q>{message.rawTranscript}</q>
            </details>
          ) : null}
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
