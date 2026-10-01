import { useEffect, useRef, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';
import { listAgents, startCall, getCall, endCall } from '../api.js';
import { TOPIC_TRANSCRIPT, decodeTranscript } from '../livekit.js';
import Transcript from '../components/Transcript.jsx';

// Part D: pick an agent, click Call, talk through the mic, live transcript.
export default function Call() {
  const [agents, setAgents] = useState([]);
  const [agentId, setAgentId] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [lines, setLines] = useState([]);
  const [muted, setMuted] = useState(false);
  const [result, setResult] = useState(null);
  const [inCall, setInCall] = useState(false);
  const roomRef = useRef(null);
  const callRef = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => {
    listAgents().then(a => { setAgents(a); if (a[0]) setAgentId(a[0].id); })
      .catch(e => setError(String(e)));
    return () => { if (roomRef.current) roomRef.current.disconnect(); };
  }, []);

  async function onCall() {
    setError(''); setLines([]); setResult(null);
    try {
      setStatus('creating call…');
      const call = await startCall(agentId);
      callRef.current = call.call_id;
      setStatus(`connecting to ${call.room} (agent dispatched: ${call.agent_dispatched})…`);
      const room = new Room();
      roomRef.current = room;
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) track.attach(audioRef.current);
      });
      room.on(RoomEvent.DataReceived, (payload, _p, _k, topic) => {
        if (topic !== TOPIC_TRANSCRIPT) return;
        try {
          const m = decodeTranscript(payload);
          setLines(prev => [...prev, {speaker: m.speaker, text: m.text}]);
        } catch (e) { setError('bad transcript payload: ' + e); }
      });
      room.on(RoomEvent.Disconnected, () => setStatus(s => s.startsWith('ended') ? s : 'disconnected'));
      await room.connect(call.url, call.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setInCall(true);
      setStatus(`in call ${call.call_id} — talk now`);
    } catch (e) { setError(String(e)); setStatus('error'); }
  }

  async function onHangup() {
    try {
      const id = callRef.current;
      if (roomRef.current) await roomRef.current.disconnect();
      setInCall(false);
      // End the call server-side (runs both compliance checks), then render
      // ONLY the persisted GET result — single source of truth.
      setStatus('ending call… (compliance checks run, may take ~30s)');
      await endCall(id);
      const full = await getCall(id);
      setResult({compliance: full.compliance, latency: full.latency});
      setStatus(`ended ${id}`);
    } catch (e) { setError(String(e)); }
  }

  return (
    <section>
      <h2>Customer call</h2>
      <div className="row">
        <label>Agent
          <select value={agentId} onChange={e => setAgentId(e.target.value)}>
            {agents.map(a => <option key={a.id} value={a.id}>{a.name} ({a.id})</option>)}
          </select>
        </label>
        {!inCall
          ? <button onClick={onCall} disabled={!agentId}>Call</button>
          : <button onClick={onHangup}>Hang up</button>}
        <button onClick={() => {
          const next = !muted;
          if (audioRef.current) audioRef.current.muted = next;
          setMuted(next);
        }}>
          {muted ? 'Unmute playback' : 'Mute playback'}
        </button>
      </div>
      <p className="status">{status}</p>
      {error && <p className="error">{error}</p>}
      {inCall && <p className="muted">Call is live — navigating away (e.g. to Supervise) disconnects this page. Use a second browser tab/window for the supervisor, per the two-page demo flow.</p>}
      <h3>Live transcript</h3>
      <Transcript lines={lines} />
      <audio ref={audioRef} autoPlay />
      {result && <CallResult result={result} />}
    </section>
  );
}

function CallResult({ result }) {
  const rec = result.compliance?.recording;
  const ref = result.compliance?.refund;
  if (!result.compliance) return <div className="card"><h3>Call result</h3><p className="muted">Compliance not available for this call.</p></div>;
  return (
    <div className="card">
      <h3>Call result</h3>
      <p>Recording disclosure (deterministic, 30s): <b>{String(rec?.pass)}</b>
        {rec?.evidence ? <> — “{rec.evidence}”</> : null}</p>
      <p>Refund promise (LLM judge): <b>{String(ref?.pass)}</b>
        {ref?.offending_line ? <> — “{ref.offending_line}”</> : null}
        {ref?.error ? <> — error: {ref.error}</> : null}</p>
      {result.latency && (
        <table>
          <thead><tr><th>turn</th><th>stt ms</th><th>llm ms</th><th>tts ms</th><th>publish ms</th></tr></thead>
          <tbody>
            {result.latency.map(t => (
              <tr key={t.turn}><td>{t.turn}</td><td>{fmt(t.stt_ms)}</td><td>{fmt(t.llm_ms)}</td><td>{fmt(t.tts_ms)}</td><td>{fmt(t.publish_ms)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const fmt = v => v == null ? '—' : v.toFixed(1);
