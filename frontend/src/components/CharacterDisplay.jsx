export default function CharacterDisplay({ item, className = '' }) {
  if (item.characters) {
    return <span className={className}>{item.characters}</span>;
  }

  if (item.character_image) {
    return (
      <img
        src={item.character_image}
        alt={item.slug || ''}
        className={`${className} character-image`}
      />
    );
  }

  return (
    <span className={`${className} character-slug`}>
      {item.slug || '?'}
    </span>
  );
}
