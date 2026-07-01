import { useEffect, useState } from "react";
import {
  getFriends,
  sendFriendRequest,
  respondFriendRequest,
  removeFriend,
  getFriendCompare,
} from "../api/client.js";
import { EmptyState, ErrorNote, SectionCard, StatTile, Tag } from "../components/ui.jsx";

function pct(value) {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

function pickResult(name, correct) {
  return (
    <span className={`compare-pick ${correct ? "hit" : "miss"}`}>
      {correct ? "✓" : "✗"} {name}
    </span>
  );
}

export default function Friends() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [username, setUsername] = useState("");
  const [addMsg, setAddMsg] = useState("");
  const [addErr, setAddErr] = useState("");
  const [busy, setBusy] = useState(false);

  const [compareFor, setCompareFor] = useState(null);
  const [compare, setCompare] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [openCard, setOpenCard] = useState("");

  async function load() {
    try {
      setOverview(await getFriends());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    let active = true;
    getFriends()
      .then((data) => active && setOverview(data))
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  async function submitAdd(event) {
    event.preventDefault();
    setAddErr("");
    setAddMsg("");
    setBusy(true);
    try {
      const result = await sendFriendRequest(username.trim());
      setAddMsg(
        result.status === "accepted"
          ? `You're now friends with ${result.friend.display_name}.`
          : `Request sent to ${result.friend.display_name}.`
      );
      setUsername("");
      await load();
    } catch (err) {
      setAddErr(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function respond(friendshipId, accept) {
    setBusy(true);
    try {
      await respondFriendRequest(friendshipId, accept);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function unfriend(userId) {
    setBusy(true);
    try {
      await removeFriend(userId);
      if (compareFor?.user_id === userId) {
        setCompareFor(null);
        setCompare(null);
      }
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function openCompare(friend) {
    setCompareFor(friend);
    setCompare(null);
    setOpenCard("");
    setCompareLoading(true);
    try {
      setCompare(await getFriendCompare(friend.user_id));
    } catch (err) {
      setError(err.message);
    } finally {
      setCompareLoading(false);
    }
  }

  return (
    <div className="view">
      <header>
        <p className="eyebrow">Your corner</p>
        <h1 className="view-title">Friends</h1>
      </header>

      <ErrorNote message={error} />

      <SectionCard eyebrow="Add a friend" title="Send a request">
        <ErrorNote message={addErr} />
        {addMsg && <p className="form-ok">{addMsg}</p>}
        <form className="friend-add" onSubmit={submitAdd}>
          <input
            type="text"
            value={username}
            required
            placeholder="their username"
            autoCapitalize="off"
            autoCorrect="off"
            onChange={(e) => setUsername(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Send request
          </button>
        </form>
        <p className="muted friend-add-note">
          Add friends by their username — no emails involved.
        </p>
      </SectionCard>

      {loading && !overview ? null : (
        <>
          {overview?.incoming?.length > 0 && (
            <SectionCard eyebrow="Pending" title="Requests to you">
              {overview.incoming.map((r) => (
                <div className="friend-row" key={r.friendship_id}>
                  <span className="friend-name">{r.display_name}</span>
                  <div className="friend-actions">
                    <button className="btn btn-primary" disabled={busy} onClick={() => respond(r.friendship_id, true)}>
                      Accept
                    </button>
                    <button className="pick-clear" disabled={busy} onClick={() => respond(r.friendship_id, false)}>
                      Decline
                    </button>
                  </div>
                </div>
              ))}
            </SectionCard>
          )}

          <SectionCard
            eyebrow="Your crew"
            title="Friends"
            description={overview?.outgoing?.length ? `${overview.outgoing.length} request(s) still pending.` : undefined}
          >
            {(!overview?.friends || overview.friends.length === 0) && (
              <EmptyState title="No friends yet" message="Add someone by their username to compare picks." />
            )}
            {overview?.friends?.map((f) => (
              <div className="friend-row" key={f.friendship_id}>
                <span className="friend-name">{f.display_name}</span>
                <div className="friend-actions">
                  <button
                    className={`btn ${compareFor?.user_id === f.user_id ? "btn-primary" : "btn-ghost"}`}
                    disabled={busy}
                    onClick={() => openCompare(f)}
                  >
                    Compare
                  </button>
                  <button className="pick-clear" disabled={busy} onClick={() => unfriend(f.user_id)}>
                    Remove
                  </button>
                </div>
              </div>
            ))}
            {overview?.outgoing?.map((r) => (
              <div className="friend-row pending" key={r.friendship_id}>
                <span className="friend-name">{r.display_name}</span>
                <Tag>Request sent</Tag>
              </div>
            ))}
          </SectionCard>

          {compareFor && (
            <SectionCard eyebrow="Head to head" title={`You vs ${compareFor.display_name}`}>
              {compareLoading && <p className="muted">Loading comparison…</p>}
              {!compareLoading && compare && compare.shared === 0 && (
                <EmptyState title="No shared picks yet" message="Once you both pick the same fights, your rivalry shows up here." />
              )}
              {!compareLoading && compare && compare.shared > 0 && (
                <>
                  <div className="tile-row four">
                    <StatTile
                      label="Cards"
                      value={`${compare.card_record.you}–${compare.card_record.them}`}
                      hint={compare.card_record.tied ? `${compare.card_record.tied} tied` : "you–them"}
                      tone="gold"
                    />
                    <StatTile label="Shared" value={compare.shared} hint="graded picks" />
                    <StatTile
                      label="Accuracy"
                      value={`${pct(compare.you.accuracy)} · ${pct(compare.them.accuracy)}`}
                      hint="you · them"
                      tone="win"
                    />
                    <StatTile
                      label="FIGHT IQ"
                      value={`${compare.you.rating} · ${compare.them.rating}`}
                      hint="you · them"
                    />
                  </div>

                  <div className="compare-cards">
                    {compare.cards.map((card) => {
                      const open = openCard === card.event_id;
                      return (
                        <div className="compare-card" key={card.event_id}>
                          <button
                            type="button"
                            className="compare-card-head"
                            onClick={() => setOpenCard(open ? "" : card.event_id)}
                          >
                            <span className="compare-card-name">{card.event_name}</span>
                            <span className="compare-card-score">
                              {card.you_correct}–{card.them_correct}
                              <Tag tone={card.winner === "you" ? "win" : card.winner === "them" ? "warn" : "neutral"}>
                                {card.winner === "you" ? "You" : card.winner === "them" ? compareFor.display_name : "Tie"}
                              </Tag>
                            </span>
                          </button>
                          {open && (
                            <div className="compare-fights">
                              {card.fights.map((fight, i) => (
                                <div className="compare-fight" key={i}>
                                  <div className="compare-fight-bout">
                                    {fight.fighter_1} vs {fight.fighter_2}
                                    {fight.actual_winner && (
                                      <span className="muted"> · won by {fight.actual_winner}</span>
                                    )}
                                  </div>
                                  <div className="compare-fight-picks">
                                    {pickResult(fight.your_pick, fight.your_correct)}
                                    {pickResult(fight.their_pick, fight.their_correct)}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </SectionCard>
          )}
        </>
      )}
    </div>
  );
}
