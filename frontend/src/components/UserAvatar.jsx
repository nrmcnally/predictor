import { useState } from "react";
import { avatarUrl } from "../api/client.js";

/**
 * A user's profile picture, or nothing when they don't have one (callers keep
 * their text/initials fallback). `bust` forces a refetch after an upload.
 */
export function UserAvatar({ userId, bust = "", size = 24, className = "" }) {
  // Track WHICH src failed: a new bust value produces a new src, which naturally
  // isn't the failed one — no effect needed to reset.
  const [failedSrc, setFailedSrc] = useState(null);
  const src = avatarUrl(userId, bust);

  if (!src || failedSrc === src) {
    return null;
  }

  return (
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      className={`user-avatar ${className}`}
      loading="lazy"
      onError={() => setFailedSrc(src)}
    />
  );
}
