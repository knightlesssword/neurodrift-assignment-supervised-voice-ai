import { useEffect, useRef, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';
import { supervisorToken } from '../api.js';
import { TOPIC_TRANSCRIPT, TOPIC_WHISPER, decodeTranscript } from '../livekit.js';
import Transcript from '../components/Transcript.jsx';

// Part E: hidden listen (subscribe-only, publishes nothing) + private whisper
// over the supervisor-whisper data topic.
export default function Supervise() {
  const [callId, setCallId] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [lines, setLines] = useState([]);
  const [whisper, setWhisper] = useState('');
  const [joined, setJoined] = useState(false);
  const [muted, setMuted] = useState(false);
  const roomRef = useRef(null);
  const audiosRef = useRef(null);

  useEffect(() => () => { if (roomRef.current) roomRef.current.disconnect(); }, []);

  async function onJoin() {
    setError(''); setLines([]);
    try {
      setStatus('fetching supervisor token…');
      const tok = await supervisorToken(callId.trim());
      const room = new Room();
      roomRef.current = room;
      room.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
        if (track.kind !== Track.Kind.Audio) return;
        const el = document.createElement('audio');
        el.autoplay = true;
        el.muted = muted;
        el.title = participant.identity;
        track.attach(el);
        audiosRef.current.appendChild(el);
        setStatus(`listening: ${participant.identity}`);
      });
      room.on(RoomEvent.DataReceived, (payload, _p, _k, topic) => {
        if (topic !== TOPIC_TRANSCRIPT) return;
        try {
          const m = decodeTranscript(payload);
          setLines(prev => [...prev, {speaker: m.speaker, text: m.text}]);
        } catch (e) { setError('bad transcript payload: ' + e); }
      });
      room.on(RoomEvent.Disconnected, () => { setStatus('left'); setJoined(false); });
      await room.connect(tok.url, tok.token);
      // Deliberately publish nothing: no mic, no tracks.
      setJoined(true);
      setStatus(`listening to ${tok.room} (hidden, publishing nothing)`);
    } catch (e) { setError(String(e)); setStatus('error'); }
  }

  async function onSend() {
    try {
      const text = whisper.trim();
      if (!text || !roomRef.current) return;
      await roomRef.current.localParticipant.publishData(
        new TextEncoder().encode(text), {reliable: true, topic: TOPIC_WHISPER});
      setStatus('whisper sent — the agent uses it in its next reply, never reads it out');
      setWhisper('');
    } catch (e) { setError(String(e)); }
  }

  async function onLeave() {
    if (roomRef.current) await roomRef.current.disconnect();
    setJoined(false);
  }

  return (
    <section>
      <h2>Supervisor</h2>
      <p className="muted">Hidden subscribe-only join: you publish nothing, so the customer cannot tell you are here.</p>
      <div className="row">
        <label>Call ID <input value={callId} onChange={e => setCallId(e.target.value)} placeholder="call-xxxxxxxx" size="18" /></label>
        {!joined ? <button onClick={onJoin} disabled={!callId.trim()}>Listen</button> : <button onClick={onLeave}>Leave</button>}
        <button onClick={() => {
          const next = !muted;
          document.querySelectorAll('#sup-audios audio').forEach(el => { el.muted = next; });
          setMuted(next);
        }}>
          {muted ? 'Unmute playback' : 'Mute playback'}
        </button>
      </div>
      <p className="status">{status}</p>
      {error && <p className="error">{error}</p>}
      <h3>Whisper (private guidance)</h3>
      <p className="muted">Applies to the agent's <b>next</b> reply — send it <b>before</b> the customer asks the question. Guidance sent mid-generation takes effect on the following turn.</p>
      <div className="row">
        <input value={whisper} onChange={e => setWhisper(e.target.value)} placeholder="e.g. offer a 10% discount" size="44" disabled={!joined} />
        <button onClick={onSend} disabled={!joined || !whisper.trim()}>Send whisper</button>
      </div>
      <h3>Live transcript</h3>
      <Transcript lines={lines} />
      <div id="sup-audios" ref={audiosRef} />
    </section>
  );
}
