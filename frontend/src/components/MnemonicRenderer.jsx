export default function MnemonicRenderer({ text }) {
  if (!text) return null;

  const parts = [];
  let lastIndex = 0;
  let key = 0;

  const regex = /<(radical|kanji|vocabulary|meaning|reading)>(.*?)<\/\1>/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <span key={key++} className={`mnemonic-${match[1]}`}>
        {match[2]}
      </span>
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <span className="mnemonic-text">{parts}</span>;
}
