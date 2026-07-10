import { useContext, useEffect, useRef, useState } from "react";
import { AppContext } from "../AppContext.js";
import {
  getFriends,
  sendFriendRequest,
  respondFriendRequest,
  removeFriend,
  getFriendCompare,
} from "../api/client.js";
import { EmptyState, ErrorNote, SectionCard, StatTile, Tag } from "../components/ui.jsx";
import { SkeletonRows } from "../components/Skeleton.jsx";
import { UserAvatar } from "../components/UserAvatar.jsx";
import { FighterMatchup } from "../components/FighterDisplay.jsx";

function pct(value) {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

/* One labeled pick pill: whose pick + what they picked + how it went.
   state: hit | miss (graded) · neutral (committed) · hidden | none (upcoming) */
function PickChip({ who, name, state }) {
  return (
    <span className={`compare-pick ${state}`}>
      <span className="compare-pick-who">{who}</span>
      {state === "hit" && "✓ "}
      {state === "miss" && "✗ "}
      {name}
    </span>
  );
}

export default function Friends() {
  const { routeParam, reflectRoute, imageLookup, openProfile } = useContext(AppContext);
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
        reflectRoute?.("friends");
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
    reflectRoute?.("friends", friend.display_name);
    try {
      const data = await getFriendCompare(friend.user_id);
      setCompare(data);
      // The most recent card starts expanded — one less click to the good part.
      setOpenCard(data?.cards?.[0]?.event_id ?? "");
    } catch (err) {
      setError(err.message);
    } finally {
      setCompareLoading(false);
    }
  }

  // #/friends/<username> deep-links straight into that head-to-head (W7).
  const autoOpenedRef = useRef(false);
  useEffect(() => {
    if (autoOpenedRef.current || !routeParam || !overview?.friends?.length) {
      return;
    }
    const wanted = routeParam.toLowerCase();
    const match = overview.friends.find(
      (friend) => (friend.display_name || "").toLowerCase() === wanted
    );
    if (match) {
      autoOpenedRef.current = true;
      // URL-sync effect: acting on the deep-linked hash param once, ref-guarded.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      openCompare(match);
    }
    // openCompare is stable in behavior; the ref guard makes reruns no-ops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeParam, overview]);

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

      {loading && !overview ? (
        <SkeletonRows rows={3} height={64} />
      ) : (
        <>
          {overview?.incoming?.length > 0 && (
            <SectionCard eyebrow="Pending" title="Requests to you">
              {overview.incoming.map((r) => (
                <div className="friend-row" key={r.friendship_id}>
                  <span className="friend-name">
                    <UserAvatar userId={r.user_id} size={26} className="friend-row-avatar" />
                    {r.display_name}
                  </span>
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
                <span className="friend-name">
                  <UserAvatar userId={f.user_id} size={26} className="friend-row-avatar" />
                  {f.display_name}
                </span>
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
                <span className="friend-name">
                  <UserAvatar userId={r.user_id} size={26} className="friend-row-avatar" />
                  {r.display_name}
                </span>
                <Tag>Request sent</Tag>
              </div>
            ))}
          </SectionCard>

          {compareFor && (
            <SectionCard eyebrow="Head to head" title={`You vs ${compareFor.display_name}`}>
              {compareLoading && <SkeletonRows rows={3} height={64} />}
              {!compareLoading && compare?.upcoming?.length > 0 && (
                <div className="compare-upcoming">
                  <p className="compare-section-label">
                    Upcoming picks — theirs unlock once you've picked that fight
                  </p>
                  {compare.upcoming.map((card) => (
                    <div className="compare-card" key={`up-${card.event_id}`}>
                      <div className="compare-card-head static">
                        <span className="compare-card-name">{card.event_name}</span>
                        <span className="compare-card-score">
                          {card.their_hidden > 0 && (
                            <Tag>{card.their_hidden} hidden</Tag>
                          )}
                          <span className="muted">{card.event_date}</span>
                        </span>
                      </div>
                      <div className="compare-fights">
                        {card.fights.map((fight, index) => (
                          <div className="compare-fight" key={fight.fight_key || index}>
                            <FighterMatchup
                              fighter1={fight.fighter_1}
                              fighter2={fight.fighter_2}
                              imageLookup={imageLookup}
                              onFighterClick={openProfile}
                            />
                            <div className="compare-fight-side">
                              {fight.agree === true && <Tag tone="gold">Same pick</Tag>}
                              {fight.agree === false && <Tag tone="warn">Split</Tag>}
                              <div className="compare-fight-picks">
                                <PickChip
                                  who="You"
                                  name={fight.your_pick || "—"}
                                  state={fight.your_pick ? "neutral" : "none"}
                                />
                                {fight.their_pick_hidden ? (
                                  <PickChip
                                    who={compareFor.display_name}
                                    name="🔒 pick to reveal"
                                    state="hidden"
                                  />
                                ) : (
                                  <PickChip
                                    who={compareFor.display_name}
                                    name={fight.their_pick || "—"}
                                    state={fight.their_pick ? "neutral" : "none"}
                                  />
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {!compareLoading && compare && compare.shared === 0 && (
                <EmptyState title="No graded picks yet" message="Once you've both picked the same completed fights, your rivalry record shows up here." />
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
                                <div className="compare-fight" key={fight.fight_key || i}>
                                  <FighterMatchup
                                    fighter1={fight.fighter_1}
                                    fighter2={fight.fighter_2}
                                    imageLookup={imageLookup}
                                    onFighterClick={openProfile}
                                  />
                                  <div className="compare-fight-side">
                                    {fight.actual_winner && (
                                      <span className="compare-winner">
                                        won by {fight.actual_winner}
                                      </span>
                                    )}
                                    <div className="compare-fight-picks">
                                      <PickChip
                                        who="You"
                                        name={fight.your_pick}
                                        state={fight.your_correct ? "hit" : "miss"}
                                      />
                                      <PickChip
                                        who={compareFor.display_name}
                                        name={fight.their_pick}
                                        state={fight.their_correct ? "hit" : "miss"}
                                      />
                                    </div>
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
