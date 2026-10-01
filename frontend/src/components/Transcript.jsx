export default function Transcript({ lines }) {
  return (
    <div className="transcript" aria-live="polite">
      {lines.length === 0 && <div className="muted">No transcript yet — lines appear here live, labelled by speaker.</div>}
      {lines.map((l, i) => (
        <div key={i} className={`tline ${l.speaker}`}>
          <span className="who">{l.speaker === 'agent' ? 'agent' : 'user'}</span>
          <span>{l.text}</span>
        </div>
      ))}
    </div>
  );
}
