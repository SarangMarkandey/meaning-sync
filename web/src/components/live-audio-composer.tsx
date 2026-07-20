"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  api,
  type LiveSessionView,
  type PartyRole,
} from "@/lib/api";
import { roleLabel } from "@/lib/flow-presentation";

type AudioState =
  | "idle"
  | "consenting"
  | "initializing"
  | "listening"
  | "finalizing"
  | "review"
  | "saving"
  | "error";

const newRequestId = () =>
  globalThis.crypto?.randomUUID?.() ?? `audio-${Date.now()}`;

function readableMediaError(error: unknown) {
  if (error instanceof DOMException && error.name === "NotAllowedError") {
    return "Microphone permission was denied. Allow access in your browser or continue with text.";
  }
  if (error instanceof DOMException && error.name === "NotFoundError") {
    return "No microphone was found. Connect one or continue with text.";
  }
  return error instanceof Error
    ? error.message
    : "The microphone connection failed. Try again or continue with text.";
}

export function LiveAudioComposer({
  session,
  role,
  accessToken,
  disabled,
  onSession,
  onContinueWithText,
}: {
  session: LiveSessionView;
  role: PartyRole;
  accessToken: string;
  disabled: boolean;
  onSession: (session: LiveSessionView) => void;
  onContinueWithText: () => void;
}) {
  const [state, setState] = useState<AudioState>("idle");
  const [partial, setPartial] = useState("");
  const [rawTranscript, setRawTranscript] = useState("");
  const [correction, setCorrection] = useState("");
  const [editing, setEditing] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const channelRef = useRef<RTCDataChannel | null>(null);
  const timerRef = useRef<number | null>(null);
  const idleTimerRef = useRef<number | null>(null);
  const startedAtRef = useRef<Date | null>(null);
  const completedAtRef = useRef<Date | null>(null);
  const durationRef = useRef(0);
  const realtimeActiveRef = useRef(false);

  const configuration = session.audio_configuration;
  const consent = session.audio_consents?.[role];

  const clearTimers = useCallback(() => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
    timerRef.current = null;
    idleTimerRef.current = null;
  }, []);

  const cleanup = useCallback(() => {
    clearTimers();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (channelRef.current) {
      channelRef.current.onmessage = null;
      channelRef.current.onopen = null;
      channelRef.current.onerror = null;
      channelRef.current.onclose = null;
      channelRef.current.close();
    }
    channelRef.current = null;
    if (peerRef.current) {
      peerRef.current.onconnectionstatechange = null;
      peerRef.current.close();
    }
    peerRef.current = null;
    if (realtimeActiveRef.current) {
      realtimeActiveRef.current = false;
      void api.endAudioTranscription(session.id, accessToken);
    }
  }, [accessToken, clearTimers, session.id]);

  const fail = useCallback(
    (message: string) => {
      cleanup();
      setError(message);
      setState("error");
      setPartial("");
    },
    [cleanup],
  );

  useEffect(() => cleanup, [cleanup]);

  const completeTranscript = useCallback(
    (transcript: string) => {
      const finalized = transcript.trim();
      completedAtRef.current = new Date();
      durationRef.current = Math.max(
        0.1,
        (completedAtRef.current.getTime() -
          (startedAtRef.current?.getTime() ?? completedAtRef.current.getTime())) /
          1000,
      );
      cleanup();
      setPartial("");
      if (!finalized) {
        fail("No speech was detected. Try again or continue with text.");
        return;
      }
      setRawTranscript(finalized);
      setCorrection(finalized);
      setState("review");
    },
    [cleanup, fail],
  );

  const startWithSession = useCallback(
    async (current: LiveSessionView) => {
      if (disabled || current.participant_readiness[role]) return;
      if (window.isSecureContext === false) {
        fail("Microphone access requires HTTPS or http://localhost. Continue with text on this connection.");
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        fail("This browser cannot access a microphone. Continue with text.");
        return;
      }
      if (typeof RTCPeerConnection === "undefined") {
        fail("This browser does not support the required WebRTC connection. Continue with text.");
        return;
      }
      setState("initializing");
      setError(null);
      setPartial("");
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        const peer = new RTCPeerConnection();
        peerRef.current = peer;
        stream.getTracks().forEach((track) => peer.addTrack(track, stream));
        const channel = peer.createDataChannel("oai-events");
        channelRef.current = channel;
        channel.onopen = () => {
          if (idleTimerRef.current !== null) {
            window.clearTimeout(idleTimerRef.current);
            idleTimerRef.current = null;
          }
          startedAtRef.current = new Date();
          setElapsed(0);
          setState("listening");
          timerRef.current = window.setInterval(() => {
            setElapsed((value) => {
              const next = value + 1;
              if (configuration && next >= configuration.max_turn_duration_seconds) {
                window.setTimeout(() => {
                  channelRef.current?.send(
                    JSON.stringify({ type: "input_audio_buffer.commit" }),
                  );
                  streamRef.current?.getTracks().forEach((track) => track.stop());
                  setState("finalizing");
                }, 0);
              }
              return next;
            });
          }, 1000);
        };
        channel.onmessage = (event) => {
          let payload: {
            type?: string;
            delta?: string;
            transcript?: string;
            error?: { message?: string };
          };
          try {
            payload = JSON.parse(String(event.data));
          } catch {
            return;
          }
          if (payload.type === "conversation.item.input_audio_transcription.delta") {
            setPartial((value) => `${value}${payload.delta ?? ""}`);
          } else if (
            payload.type === "conversation.item.input_audio_transcription.completed"
          ) {
            completeTranscript(payload.transcript ?? "");
          } else if (payload.type === "error") {
            fail(payload.error?.message ?? "Transcription failed. Continue with text or try again.");
          }
        };
        channel.onerror = () => fail("The transcription connection failed. Try again or continue with text.");
        peer.onconnectionstatechange = () => {
          if (["failed", "disconnected"].includes(peer.connectionState)) {
            fail("The transcription connection was lost. No incomplete transcript was saved.");
          }
        };
        const offer = await peer.createOffer();
        await peer.setLocalDescription(offer);
        const answerSdp = await api.initializeAudioTranscription(
          current.id,
          offer.sdp ?? "",
          current.revision ?? 1,
          newRequestId(),
          accessToken,
        );
        realtimeActiveRef.current = true;
        idleTimerRef.current = window.setTimeout(
          () => fail("The WebRTC connection timed out. Try again or continue with text."),
          (configuration?.initialization_timeout_seconds ?? 12) * 1000,
        );
        await peer.setRemoteDescription({ type: "answer", sdp: answerSdp });
      } catch (caught) {
        fail(readableMediaError(caught));
      }
    },
    [accessToken, completeTranscript, configuration, disabled, fail, role],
  );

  const consentAndStart = async () => {
    if (!configuration) {
      fail("Audio configuration is unavailable. Refresh or continue with text.");
      return;
    }
    setState("consenting");
    setError(null);
    try {
      const next = await api.recordAudioConsent(
        session.id,
        configuration.consent_notice_version,
        session.revision ?? 1,
        newRequestId(),
        accessToken,
      );
      onSession(next);
      await startWithSession(next);
    } catch (caught) {
      fail(readableMediaError(caught));
    }
  };

  const stopAndReview = () => {
    if (!channelRef.current || channelRef.current.readyState !== "open") {
      fail("The transcription connection is not ready. Try again or continue with text.");
      return;
    }
    clearTimers();
    channelRef.current.send(JSON.stringify({ type: "input_audio_buffer.commit" }));
    streamRef.current?.getTracks().forEach((track) => track.stop());
    setState("finalizing");
    idleTimerRef.current = window.setTimeout(
      () => fail("No finalized transcript arrived. Try again or continue with text."),
      (configuration?.idle_timeout_seconds ?? 20) * 1000,
    );
  };

  const reset = () => {
    cleanup();
    setState("idle");
    setRawTranscript("");
    setCorrection("");
    setEditing(false);
    setPartial("");
    setError(null);
  };

  const addTranscript = async () => {
    if (!consent || !configuration || !startedAtRef.current || !completedAtRef.current) {
      fail("The reviewed transcript is missing required provenance. Record it again.");
      return;
    }
    const corrected = correction.trim();
    setState("saving");
    try {
      const next = await api.addAudioTranscript(
        session.id,
        {
          raw_transcript: rawTranscript,
          ...(corrected !== rawTranscript ? { corrected_text: corrected } : {}),
          started_at: startedAtRef.current.toISOString(),
          completed_at: completedAtRef.current.toISOString(),
          duration_seconds: durationRef.current,
          transcription_model: configuration.model,
          consent_id: consent.id,
          expected_revision: session.revision ?? 1,
          request_id: newRequestId(),
        },
        accessToken,
      );
      onSession(next);
      reset();
    } catch (caught) {
      fail(readableMediaError(caught));
    }
  };

  if (!consent) {
    return (
      <section className="audio-consent" aria-labelledby="audio-consent-title">
        <p className="eyebrow">{roleLabel(role)}’s audio consent</p>
        <h3 id="audio-consent-title">Review before using the microphone</h3>
        <p>
          MeaningSync will send your speech to OpenAI for transcription.
          MeaningSync stores the transcript as conversation evidence but does not
          save the raw audio recording.
        </p>
        <details>
          <summary>Review privacy notice</summary>
          <p>Consent is recorded for this participant, this Live session and the current notice version. You can stop microphone use at any time.</p>
        </details>
        <div className="audio-actions">
          <button className="button primary" type="button" disabled={disabled || state === "consenting"} onClick={() => void consentAndStart()}>
            {state === "consenting" ? "Recording consent…" : "I consent and enable microphone"}
          </button>
          <button className="button secondary" type="button" onClick={onContinueWithText}>Continue with text instead</button>
        </div>
      </section>
    );
  }

  return (
    <section className="audio-composer" aria-labelledby="audio-turn-title">
      <div className="audio-turn-heading">
        <div>
          <p className="eyebrow">Role-specific recording</p>
          <h3 id="audio-turn-title">{roleLabel(role)}’s turn</h3>
        </div>
        <span>{Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}</span>
      </div>
      <p className="audio-status" role="status" aria-live="polite">
        {state === "initializing" && "Connecting securely to transcription…"}
        {state === "listening" && "Listening… microphone active"}
        {state === "finalizing" && "Finalizing transcript…"}
        {state === "idle" && "Microphone is off."}
        {state === "review" && "Microphone is off. Review before adding."}
        {state === "saving" && "Adding finalized transcript…"}
        {state === "error" && "Microphone is off."}
      </p>
      {partial && state !== "review" ? <div className="partial-transcript" aria-live="polite"><span>Live transcript</span><p>{partial}</p></div> : null}
      {state === "idle" ? (
        <button className="button primary record-action" type="button" disabled={disabled} onClick={() => void startWithSession(session)}>Start speaking</button>
      ) : null}
      {state === "listening" ? <button className="button primary record-action listening" type="button" onClick={stopAndReview}>Stop and review</button> : null}
      {state === "initializing" || state === "finalizing" ? <button className="button primary record-action" type="button" disabled>{state === "initializing" ? "Starting microphone…" : "Preparing review…"}</button> : null}
      {state === "review" || state === "saving" ? (
        <div className="transcript-review">
          <span>Transcript</span>
          <blockquote>{rawTranscript}</blockquote>
          {editing ? <label htmlFor="transcript-correction">Correct transcript<textarea id="transcript-correction" rows={4} maxLength={configuration?.max_transcript_length ?? 2000} value={correction} onChange={(event) => setCorrection(event.target.value)} /></label> : null}
          <div className="audio-actions">
            <button className="button primary" type="button" disabled={state === "saving" || correction.trim().length < 2} onClick={() => void addTranscript()}>Add to conversation</button>
            <button className="button secondary" type="button" disabled={state === "saving"} onClick={() => setEditing(true)}>Correct transcript</button>
            <button className="text-action" type="button" disabled={state === "saving"} onClick={() => { reset(); void startWithSession(session); }}>Record again</button>
            <button className="text-action" type="button" disabled={state === "saving"} onClick={reset}>Cancel</button>
          </div>
        </div>
      ) : null}
      {error ? (
        <div className="audio-error" role="alert">
          <p>{error}</p>
          <div className="audio-actions">
            <button className="button secondary" type="button" onClick={reset}>Try again</button>
            <button className="text-action" type="button" onClick={() => { reset(); onContinueWithText(); }}>Continue with text</button>
          </div>
        </div>
      ) : null}
      <small>Only the finalized transcript is added. MeaningSync does not save raw audio.</small>
    </section>
  );
}
