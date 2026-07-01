import { useEffect, useState } from "react";
import { getUserLeaderboard } from "../api/client.js";
import {
  EmptyState,
  ErrorNote,
  SectionCard,
  Spinner,
  StatTile,
  Tag,
} from "../components/ui.jsx";

function accuracyText(value) {
  return value === null || value === undefined ? "-" : `${Math.round(value * 100)}%`;
}

function publicDisplayName(row) {
  const displayName = String(row.display_name || row.name || "").trim();
  return displayName && !displayName.includes("@") ? displayName : "Unnamed User";
}

function recordText(row) {
  return row && row.graded > 0 ? `${row.wins}-${row.losses}` : "-";
}

function rankSummary(row) {
  if (!row) {
    return "Turn on your public profile and make picks to appear here.";
  }

  if (!row.provisional) {
    return `${row.graded} graded picks in your public record.`;
  }

  const remaining = Number(row.picks_until_established);
  if (Number.isFinite(remaining) && remaining > 0) {
    return `${remaining} more graded pick${remaining === 1 ? "" : "s"} until your rating is established.`;
  }

  return "Your rating is still provisional.";
}

export default function UserLeaderboard() {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    getUserLeaderboard()
      .then((leaderboard) => {
        if (active) {
          setRows(leaderboard);
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
          setRows([]);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const myRow = rows?.find((row) => row.is_me);

  return (
    <div className="view leaderboards">
      <header className="view-head">
        <div>
          <p className="eyebrow">User predictions</p>
          <h1 className="view-title">User Leaderboard</h1>
        </div>
      </header>

      <ErrorNote message={error} />

      {loading && <Spinner label="Ranking users..." />}

      {!loading && rows && (
        <SectionCard
          eyebrow="Your standing"
          title={myRow ? "Current rank" : "Not ranked yet"}
          description={rankSummary(myRow)}
          className="user-leaderboard-summary"
        >
          <div className="tile-row four">
            <StatTile label="Rank" value={myRow ? `#${myRow.rank}` : "-"} hint="public" tone="gold" />
            <StatTile label="FIGHT IQ" value={myRow?.rating ?? "-"} hint="rating" />
            <StatTile label="Record" value={recordText(myRow)} hint="W-L" />
            <StatTile
              label="Accuracy"
              value={myRow ? accuracyText(myRow.accuracy) : "-"}
              hint="win rate"
            />
          </div>
          {myRow?.provisional && (
            <div className="leaderboard-summary-tags">
              <Tag>Provisional</Tag>
            </div>
          )}
        </SectionCard>
      )}

      {!loading && rows && rows.length === 0 && (
        <EmptyState
          title="No public prediction records yet"
          message="Make your profile public and start picking to appear here."
        />
      )}

      {!loading && rows && rows.length > 0 && (
        <div className="leaderboard-list">
          {rows.map((row) => {
            const displayName = publicDisplayName(row);

            return (
              <div
                className={`leaderboard-row ${row.rank <= 3 ? `podium-${row.rank}` : ""} ${
                  row.is_me ? "is-me" : ""
                }`}
                key={`${row.rank}-${displayName}`}
              >
                <span className="rank-medal">#{row.rank}</span>

                <div className="leaderboard-fighter">
                  <span className="fighter-name-text">
                    {displayName}
                    {row.is_me && <Tag tone="gold" className="lb-you">You</Tag>}
                    {row.provisional && <Tag>Provisional</Tag>}
                  </span>
                  <span className="muted">
                    {row.wins}-{row.losses} - {row.graded} graded
                  </span>
                </div>

                <div className="leaderboard-score">
                  <span className="stat-label">FIGHT IQ</span>
                  <strong className="mono">{row.rating}</strong>
                </div>

                <div className="leaderboard-stats">
                  <Tag>Accuracy: {accuracyText(row.accuracy)}</Tag>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
