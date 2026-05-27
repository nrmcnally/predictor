export function normalizeFighterName(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

export function getFighterInitials(name) {
  const parts = String(name || "")
    .replaceAll("-", " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (parts.length === 0) {
    return "?";
  }

  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }

  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function getFighterImageData(fighterName, fighterImageLookup = {}) {
  const name = String(fighterName || "").trim();
  const key = normalizeFighterName(name);
  const imageData = fighterImageLookup[key] || {};

  const imageUrl =
    imageData.image_url ||
    imageData.fighter_image_url ||
    imageData.url ||
    "";

  return {
    name,
    imageUrl,
    sourceUrl:
      imageData.source_url ||
      imageData.fighter_image_source_url ||
      "",
    initials:
      imageData.initials ||
      imageData.fighter_initials ||
      getFighterInitials(name),
    available:
      Boolean(imageUrl) ||
      Boolean(imageData.image_available) ||
      Boolean(imageData.fighter_image_available),
  };
}

export function FighterAvatar({
  name,
  imageLookup = {},
  size = "sm",
}) {
  const imageData = getFighterImageData(name, imageLookup);
  const className = `fighter-avatar ${size} ${
    imageData.imageUrl ? "has-image" : "placeholder"
  }`;

  if (imageData.imageUrl) {
    return (
      <img
        className={className}
        src={imageData.imageUrl}
        alt={`${imageData.name || "Fighter"} headshot`}
        loading="lazy"
        onError={(event) => {
          event.currentTarget.style.display = "none";
          const fallback = event.currentTarget.nextElementSibling;

          if (fallback) {
            fallback.style.display = "inline-flex";
          }
        }}
      />
    );
  }

  return (
    <span className={className} aria-hidden="true">
      {imageData.initials}
    </span>
  );
}

export function FighterName({
  name,
  imageLookup = {},
  size = "sm",
  className = "",
  onClick,
}) {
  const imageData = getFighterImageData(name, imageLookup);
  const isClickable = typeof onClick === "function" && Boolean(imageData.name);

  function handleClick(event) {
    if (!isClickable) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    onClick(imageData.name);
  }

  function handleKeyDown(event) {
    if (!isClickable) {
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      handleClick(event);
    }
  }

  return (
    <span
      className={`fighter-name ${isClickable ? "clickable" : ""} ${className}`}
      role={isClickable ? "button" : undefined}
      tabIndex={isClickable ? 0 : undefined}
      title={isClickable ? `Open ${imageData.name} profile` : undefined}
      onClick={isClickable ? handleClick : undefined}
      onKeyDown={isClickable ? handleKeyDown : undefined}
    >
      <span className="fighter-avatar-wrap">
        <FighterAvatar name={name} imageLookup={imageLookup} size={size} />
        {imageData.imageUrl && (
          <span
            className={`fighter-avatar ${size} placeholder`}
            style={{ display: "none" }}
            aria-hidden="true"
          >
            {imageData.initials}
          </span>
        )}
      </span>
      <span className="fighter-name-text">{imageData.name || "Unknown fighter"}</span>
    </span>
  );
}

export function FighterMatchup({
  fighter1,
  fighter2,
  imageLookup = {},
  onFighterClick,
}) {
  return (
    <span className="fighter-matchup">
      <FighterName
        name={fighter1}
        imageLookup={imageLookup}
        onClick={onFighterClick}
      />
      <span className="fighter-matchup-vs">vs</span>
      <FighterName
        name={fighter2}
        imageLookup={imageLookup}
        onClick={onFighterClick}
      />
    </span>
  );
}
