import { useEffect, useRef } from "react";

// Browser Speech Recognition API (Chrome, Edge, Safari; not in all TS libs)
interface SpeechRecognitionResultList {
  length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}
interface SpeechRecognitionResult {
  length: number;
  item(index: number): SpeechRecognitionResultItem;
  [index: number]: SpeechRecognitionResultItem;
  isFinal: boolean;
}
interface SpeechRecognitionResultItem {
  transcript: string;
  confidence: number;
}
interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
}
declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  }
}

type UseUserTranscriptArgs = {
  socketStatus: "connected" | "disconnected" | "connecting";
  sendMessage: (msg: { type: "metadata"; data: { userText: string } }) => void;
};

/**
 * When the socket is connected, runs browser SpeechRecognition and sends
 * recognized user speech to the server as metadata.userText so the handoff
 * transcript can include "User: ..." as well as "Agent: ...".
 */
export function useUserTranscript({
  socketStatus,
  sendMessage,
}: UseUserTranscriptArgs) {
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  useEffect(() => {
    const SpeechRecognitionClass =
      window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SpeechRecognitionClass || socketStatus !== "connected") {
      return;
    }

    const recognition = new SpeechRecognitionClass();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const result = event.results[event.resultIndex];
      if (result.isFinal && result.length > 0) {
        const transcript = result[0].transcript?.trim();
        if (transcript) {
          sendMessage({ type: "metadata", data: { userText: transcript } });
        }
      }
    };

    recognition.onerror = () => {
      // Ignore no-speech and other non-fatal errors
    };

    recognition.start();
    recognitionRef.current = recognition;

    return () => {
      try {
        recognition.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    };
  }, [socketStatus, sendMessage]);
}

