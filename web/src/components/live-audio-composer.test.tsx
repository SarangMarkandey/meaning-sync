import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveAudioComposer } from "@/components/live-audio-composer";
import { api, type LiveSessionView } from "@/lib/api";
import { guidedV5Session } from "@/test/fixtures/live-guided";

const stopTrack = vi.fn();
const sendEvent = vi.fn();
const closeChannel = vi.fn();
const closePeer = vi.fn();
let channel: {
  readyState: RTCDataChannelState;
  onopen: (() => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: (() => void) | null;
  onclose: (() => void) | null;
  send: typeof sendEvent;
  close: typeof closeChannel;
};

class FakePeerConnection {
  connectionState: RTCPeerConnectionState = "connected";
  onconnectionstatechange: (() => void) | null = null;
  addTrack = vi.fn();
  close = closePeer;
  createDataChannel() {
    return channel as unknown as RTCDataChannel;
  }
  async createOffer() {
    return { type: "offer" as RTCSdpType, sdp: "v=0\r\ns=test-offer\r\n" };
  }
  async setLocalDescription() {}
  async setRemoteDescription() {
    channel.onopen?.();
  }
}

const stream = {
  getTracks: () => [{ stop: stopTrack }],
} as unknown as MediaStream;

function audioSession(consented = true): LiveSessionView {
  const base = guidedV5Session({
    stage: "conversation_draft",
    agreement_versions: [],
    current_agreement_version_id: null,
    questions: [],
    active_participant_id: null,
    guidance: {
      ...guidedV5Session().guidance,
      user_stage: "conversation",
      active_question_id: null,
      active_clarification_id: null,
    },
  });
  return {
    ...base,
    audio_consents: consented
      ? {
          hirer: {
            id: "audio-consent-1",
            session_id: base.id,
            participant_role: "hirer",
            notice_version: "audio-transcription-v1",
            consented_at: "2026-07-19T10:00:00Z",
            request_id: "consent-request",
          },
        }
      : {},
  };
}

describe("LiveAudioComposer", () => {
  beforeEach(() => {
    channel = {
      readyState: "open",
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
      send: sendEvent,
      close: closeChannel,
    };
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue(stream) },
    });
    vi.stubGlobal(
      "RTCPeerConnection",
      FakePeerConnection as unknown as typeof RTCPeerConnection,
    );
    vi.spyOn(api, "initializeAudioTranscription").mockResolvedValue(
      "v=0\r\ns=test-answer\r\n",
    );
    vi.spyOn(api, "endAudioTranscription").mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    stopTrack.mockReset();
    sendEvent.mockReset();
    closeChannel.mockReset();
    closePeer.mockReset();
  });

  it("requests microphone permission only after persisted consent", async () => {
    let resolveConsent: ((value: LiveSessionView) => void) | undefined;
    vi.spyOn(api, "recordAudioConsent").mockReturnValue(
      new Promise((resolve) => {
        resolveConsent = resolve;
      }),
    );
    render(
      <LiveAudioComposer
        session={audioSession(false)}
        role="hirer"
        accessToken="role-token"
        disabled={false}
        onSession={vi.fn()}
        onContinueWithText={vi.fn()}
      />,
    );
    expect(screen.getByText(/send your speech to OpenAI/)).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "I consent and enable microphone" }),
    );
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
    resolveConsent?.(audioSession(true));
    await waitFor(() =>
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
        audio: true,
      }),
    );
  });

  it("finalizes, corrects and submits a reviewed transcript", async () => {
    const updated = audioSession(true);
    const submit = vi.spyOn(api, "addAudioTranscript").mockResolvedValue(updated);
    render(
      <LiveAudioComposer
        session={updated}
        role="hirer"
        accessToken="role-token"
        disabled={false}
        onSession={vi.fn()}
        onContinueWithText={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Start speaking" }));
    expect(await screen.findByText(/Listening… microphone active/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Stop and review" }));
    expect(sendEvent).toHaveBeenCalledWith(
      JSON.stringify({ type: "input_audio_buffer.commit" }),
    );
    channel.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify({
          type: "conversation.item.input_audio_transcription.completed",
          transcript: "The price is twelve hundred rupees.",
        }),
      }),
    );
    expect(await screen.findByText("Transcript")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Correct transcript" }));
    fireEvent.change(screen.getByLabelText("Correct transcript"), {
      target: { value: "The price is ₹1,200." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add to conversation" }));
    await waitFor(() => expect(submit).toHaveBeenCalled());
    expect(submit.mock.calls[0][1]).toMatchObject({
      raw_transcript: "The price is twelve hundred rupees.",
      corrected_text: "The price is ₹1,200.",
      transcription_model: "gpt-realtime-whisper",
      consent_id: "audio-consent-1",
    });
  });

  it("recovers to text when permission is denied", async () => {
    const fallback = vi.fn();
    vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(
      new DOMException("denied", "NotAllowedError"),
    );
    render(
      <LiveAudioComposer
        session={audioSession(true)}
        role="hirer"
        accessToken="role-token"
        disabled={false}
        onSession={vi.fn()}
        onContinueWithText={fallback}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Start speaking" }));
    expect(await screen.findByText(/permission was denied/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Continue with text" }));
    expect(fallback).toHaveBeenCalledOnce();
  });

  it("stops tracks and closes WebRTC resources on unmount", async () => {
    const rendered = render(
      <LiveAudioComposer
        session={audioSession(true)}
        role="hirer"
        accessToken="role-token"
        disabled={false}
        onSession={vi.fn()}
        onContinueWithText={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Start speaking" }));
    await screen.findByText(/Listening… microphone active/);
    rendered.unmount();
    expect(stopTrack).toHaveBeenCalled();
    expect(closeChannel).toHaveBeenCalled();
    expect(closePeer).toHaveBeenCalled();
  });
});
