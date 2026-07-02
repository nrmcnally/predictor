/**
 * THE leaderboard row — previously re-implemented (and drifting) in three
 * places: fighter Leaderboards, the User Leaderboard, and My Picks' card
 * boards. Callers compose the identity cell (`leading`); rank/podium/is-me,
 * the score cell, and the stats cell are structural and identical everywhere.
 */
export function LeaderboardRow({
  rank,
  isMe = false,
  withAvatar = false,
  leading,
  scoreLabel,
  scoreValue,
  scoreTitle,
  stats = null,
  className = "",
}) {
  return (
    <div
      className={`leaderboard-row ${rank <= 3 ? `podium-${rank}` : ""} ${
        isMe ? "is-me" : ""
      } ${className}`}
    >
      <span className="rank-medal">#{rank}</span>

      <div className={`leaderboard-fighter ${withAvatar ? "lb-with-avatar" : ""}`}>
        {leading}
      </div>

      <div className="leaderboard-score">
        <span className="stat-label" title={scoreTitle}>
          {scoreLabel}
        </span>
        <strong className="mono">{scoreValue}</strong>
      </div>

      <div className="leaderboard-stats">{stats}</div>
    </div>
  );
}
