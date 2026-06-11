import { getFighterInitials, normalizeFighterName } from "../lib/format.js";

function getFighterImageData(fighterName, imageLookup = {}) {
  const name = String(fighterName || "").trim();
  const imageData = imageLookup[normalizeFighterName(name)] || {};
  const imageUrl =
    imageData.image_url || imageData.fighter_image_url || imageData.url || "";

  return {
    name,
    imageUrl,
    initials:
      imageData.initials || imageData.fighter_initials || getFighterInitials(name),
  };
}

function avatarHue(name) {
  let hash = 0;

  for (const character of String(name || "")) {
    hash = (hash * 31 + character.charCodeAt(0)) % 360;
  }

  return hash;
}

export function FighterAvatar({ name, imageLookup = {}, size = "sm", corner }) {
  const imageData = getFighterImageData(name, imageLookup);
  const cornerClass = corner ? `corner-${corner}` : "";

  if (imageData.imageUrl) {
    return (
      <span className={`avatar size-${size} ${cornerClass}`}>
        <img
          src={imageData.imageUrl}
          alt={`${imageData.name || "Fighter"} headshot`}
          loading="lazy"
          onError={(event) => {
            event.currentTarget.style.display = "none";
            event.currentTarget.parentElement.dataset.fallback = "true";
          }}
        />
        <span className="avatar-fallback">{imageData.initials}</span>
      </span>
    );
  }

  return (
    <span
      className={`avatar size-${size} ${cornerClass}`}
      data-fallback="true"
      style={{ "--avatar-hue": avatarHue(imageData.name) }}
    >
      <span className="avatar-fallback">{imageData.initials}</span>
    </span>
  );
}

export function FighterName({
  name,
  imageLookup = {},
  size = "sm",
  corner,
  onClick,
  className = "",
}) {
  const imageData = getFighterImageData(name, imageLookup);
  const clickable = typeof onClick === "function" && Boolean(imageData.name);

  const content = (
    <>
      <FighterAvatar name={name} imageLookup={imageLookup} size={size} corner={corner} />
      <span className="fighter-name-text">{imageData.name || "Unknown fighter"}</span>
    </>
  );

  if (clickable) {
    return (
      <button
        type="button"
        className={`fighter-name clickable ${className}`}
        title={`Open ${imageData.name} profile`}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onClick(imageData.name);
        }}
      >
        {content}
      </button>
    );
  }

  return <span className={`fighter-name ${className}`}>{content}</span>;
}

export function FighterMatchup({ fighter1, fighter2, imageLookup = {}, onFighterClick }) {
  return (
    <span className="fighter-matchup">
      <FighterName
        name={fighter1}
        imageLookup={imageLookup}
        corner="red"
        onClick={onFighterClick}
      />
      <span className="matchup-vs">vs</span>
      <FighterName
        name={fighter2}
        imageLookup={imageLookup}
        corner="blue"
        onClick={onFighterClick}
      />
    </span>
  );
}
