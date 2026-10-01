// Shared LiveKit constants. Must match agent/worker.py and web/*.html.
export const TOPIC_TRANSCRIPT = 'transcript';
export const TOPIC_WHISPER = 'supervisor-whisper';

export function decodeTranscript(payload) {
  return JSON.parse(new TextDecoder().decode(payload));
}
