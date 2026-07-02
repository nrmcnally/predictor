import { useState } from "react";
import { getUserLeaderboard } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { LeaderboardRow } from "../components/LeaderboardRow.jsx";
import { UserAvatar } from "../components/UserAvatar.jsx";
import {
  EmptyState,
  ErrorNote,
  SectionCard,
  Spinner,
  StatTile,
  Tag,
} from "../components/ui.jsx";

const SCOPES = [
  { value: "overall", label: "Overall" },
  { value: "friends", label: "Friends" },
  { value: "me", label: "Me" },
];

const WINDOWS = [
  { value: "all_time", label: "All-time" },
  { value: "last5", label: "Last 5 cards" },
  { value: "current_month", label: "This month" },
];

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

function emptyMessage(scope, timeWindow) {
  if (scope === "friends") {
    return "Add friends and score shared picks to build a private leaderboard.";
  }
  if (scope === "me") {
    return "Make picks on upcoming cards, then check back after results are scored.";
  }
  if (timeWindow !== "all_time") {
    return "No public users have scored picks in this window yet.";
  }
  return "Make your profile public and start picking to appear here.";
}

function viewDescription(scope, timeWindow) {
  const scopeText =
    scope === "friends"
      ? "Accepted friends plus you."
      : scope === "me"
        ? "Only your scored picks."
        : "Public opt-in users only.";
  const windowText =
    timeWindow === "last5"
      ? "Filtered to the latest five scored cards in this view."
      : timeWindow === "current_month"
        ? "Filtered to cards scored this month."
        : "All scored picks.";
  return `${scopeText} ${windowText}`;
}

export default function UserLeaderboard() {
  const [scope, setScope] = useState("overall");
  const [timeWindow, setTimeWindow] = useState("all_time");
  const { data: rows, loading, error } = useApi(
    () => getUserLeaderboard({ scope, window: timeWindow }),
    [scope, timeWindow]
  );

  const chooseScope = (nextScope) => nextScope !== scope && setScope(nextScope);
  const chooseWindow = (nextWindow) =>
    nextWindow !== timeWindow && setTimeWindow(nextWindow);

  const myRow = rows?.find((row) => row.is_me);
  const totalGraded = rows?.reduce((sum, row) => sum + Number(row.graded || 0), 0) ?? 0;

  return (
    <div className="view leaderboards">
      <header className="view-head">
        <div>
          <p className="eyebrow">User predictions</p>
          <h1 className="view-title">User Leaderboard</h1>
        </div>
      </header>

      <ErrorNote message={error} />

      <SectionCard className="leaderboard-controls-card">
        <div className="user-leaderboard-controls">
          <div className="segmented user-lb-tabs" aria-label="Leaderboard scope">
            {SCOPES.map((option) => (
              <button
                key={option.value}
                type="button"
                className={scope === option.value ? "active" : ""}
                onClick={() => chooseScope(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="segmented user-lb-tabs" aria-label="Leaderboard window">
            {WINDOWS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={timeWindow === option.value ? "active" : ""}
                onClick={() => chooseWindow(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </SectionCard>

      {loading && <Spinner label="Ranking users..." />}

      {!loading && rows && (
        <SectionCard
          eyebrow="Your standing"
          title={myRow ? "Current rank" : "Not ranked yet"}
          description={`${rankSummary(myRow)} ${viewDescription(scope, timeWindow)}`}
          className="user-leaderboard-summary"
        >
          <div className="tile-row four">
            <StatTile label="Rank" value={myRow ? `#${myRow.rank}` : "-"} hint={scope} tone="gold" />
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
              {myRow.picks_until_established > 0 && (
                <Tag>{myRow.picks_until_established} picks to establish</Tag>
              )}
            </div>
          )}
        </SectionCard>
      )}

      {!loading && rows && rows.length === 0 && (
        <EmptyState
          title="No scored records yet"
          message={emptyMessage(scope, timeWindow)}
        />
      )}

      {!loading && rows && rows.length > 0 && (
        <>
          <div className="leaderboard-window-note">
            <Tag>{WINDOWS.find((item) => item.value === timeWindow)?.label}</Tag>
            <span>{rows.length} users - {totalGraded} scored picks in view</span>
          </div>

          <div className="leaderboard-list">
            {rows.map((row) => {
              const displayName = publicDisplayName(row);

              return (
                <LeaderboardRow
                  key={`${row.rank}-${displayName}`}
                  rank={row.rank}
                  isMe={row.is_me}
                  withAvatar
                  scoreLabel="FIGHT IQ"
                  scoreValue={row.rating}
                  leading={
                    <>
                      <UserAvatar userId={row.user_id} size={38} className="lb-avatar" />
                      <div className="lb-copy">
                        <span className="fighter-name-text">
                          {displayName}
                          {row.is_me && <Tag tone="gold" className="lb-you">You</Tag>}
                          {row.provisional && <Tag>Provisional</Tag>}
                        </span>
                        <span className="muted">
                          {row.wins}-{row.losses} - {row.graded} graded
                        </span>
                      </div>
                    </>
                  }
                  stats={
                    <>
                      <Tag>Accuracy: {accuracyText(row.accuracy)}</Tag>
                      {row.picks_until_established > 0 && (
                        <Tag>{row.picks_until_established} to establish</Tag>
                      )}
                    </>
                  }
                />
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
