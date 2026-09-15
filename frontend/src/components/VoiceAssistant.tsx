"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, X } from "lucide-react";
import {
  isSpeechRecognitionSupported,
  isSpeechSynthesisSupported,
  useSpeechRecognition,
} from "@/lib/useSpeechRecognition";
import type { Message } from "@/lib/types";

const SILENCE_MS = 1100;

interface VoiceAssistantProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (text: string) => void;
  isStreaming: boolean;
  latestAssistantMessage: Message | null;
}

export default function VoiceAssistant({ open, onClose, onSubmit, isStreaming, latestAssistantMessage }: VoiceAssistantProps) {
  const [phase, setPhase] = useState<"listening" | "thinking" | "speaking">("listening");
  const [liveTranscript, setLiveTranscript] = useState("");
  const silenceTimerRef = useRef<number | null>(null);
  const spokenIdRef = useRef<string | null>(null);
  const wasStreamingRef = useRef(false);

  const { supported, listening, start, stop } = useSpeechRecognition({
    continuous: true,
    onResult: (transcript, isFinal) => {
      setLiveTranscript(transcript);
      if (silenceTimerRef.current) window.clearTimeout(silenceTimerRef.current);
      if (isFinal && transcript.trim()) {
        silenceTimerRef.current = window.setTimeout(() => {
          const text = transcript.trim();
          if (!text) return;
          stop();
          setPhase("thinking");
          setLiveTranscript("");
          onSubmit(text);
        }, SILENCE_MS);
      }
    },
  });

  useEffect(() => {
    if (!open) return;
    spokenIdRef.current = latestAssistantMessage?.id ?? null;
    setPhase("listening");
    setLiveTranscript("");
    const t = window.setTimeout(() => start(), 150);
    return () => {
      window.clearTimeout(t);
      stop();
      window.speechSynthesis?.cancel();
      if (silenceTimerRef.current) window.clearTimeout(silenceTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (wasStreamingRef.current && !isStreaming && latestAssistantMessage && latestAssistantMessage.id !== spokenIdRef.current) {
      spokenIdRef.current = latestAssistantMessage.id;
      const text = latestAssistantMessage.content.trim();
      if (text && isSpeechSynthesisSupported()) {
        setPhase("speaking");
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.onend = () => {
          setPhase("listening");
          start();
        };
        utterance.onerror = () => {
          setPhase("listening");
          start();
        };
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      } else {
        setPhase("listening");
        start();
      }
    }
    wasStreamingRef.current = isStreaming;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStreaming, latestAssistantMessage, open]);

  if (!open) return null;

  const statusText =
    !supported || !isSpeechRecognitionSupported()
      ? "Voice isn't supported in this browser."
      : phase === "listening"
        ? liveTranscript || (listening ? "Listening..." : "Starting microphone...")
        : phase === "thinking"
          ? "MyBuddy is thinking..."
          : "MyBuddy is speaking...";

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-8 bg-[#0c0e1f]/97 px-6 backdrop-blur-sm">
      <button
        onClick={onClose}
        aria-label="Exit voice mode"
        className="absolute right-5 top-5 flex h-10 w-10 items-center justify-center rounded-full text-white/60 transition hover:bg-white/10 hover:text-white"
      >
        <X className="h-5 w-5" strokeWidth={2.2} />
      </button>

      <div
        className={`flex h-32 w-32 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 transition-transform duration-300 ${
          phase === "listening" && listening ? "scale-110 shadow-[0_0_0_16px_rgba(129,102,255,0.15)]" : ""
        } ${phase === "speaking" ? "animate-pulse" : ""}`}
      >
        <Mic className="h-12 w-12 text-white" strokeWidth={1.75} />
      </div>

      <p className="max-w-sm text-center text-sm leading-relaxed text-white/70">{statusText}</p>

      {(!supported || !isSpeechRecognitionSupported()) && (
        <button
          onClick={onClose}
          className="rounded-full bg-white/10 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-white/20"
        >
          Close
        </button>
      )}
    </div>
  );
}
