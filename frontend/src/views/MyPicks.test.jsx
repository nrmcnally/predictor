import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { AppContext } from "../AppContext.js";
import MyPicks from "./MyPicks.jsx";

const CARD = {
  event_id: "evt-1",
  event_name: "UFC Test Night",
  event_date: "2099-01-01",
  event_location: "Test City",
  fight_count: 1,
  lock_state: { locked: false, effective_start_at_utc: "2099-01-01T00:00:00Z" },
};

const DETAIL = {
  ...CARD,
  fights: [
    {
      fight_url: "http://fights/1",
      weight_class: "Heavyweight",
      fighter_1: "Ada Striker",
      fighter_2: "Boz Grappler",
      prediction: {
        fighter_a: "Ada Striker",
        fighter_b: "Boz Grappler",
        fighter_a_probability: 0.6,
        fighter_b_probability: 0.4,
        predicted_winner: "Ada Striker",
      },
    },
  ],
};

vi.mock(import("../api/client.js"), async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    getFutureCards: vi.fn(),
    getFutureCardPredictions: vi.fn(),
    getFutureFightOdds: vi.fn(),
    getMyPredictions: vi.fn(),
    getUserCardLeaderboard: vi.fn(),
    savePrediction: vi.fn(),
    deletePrediction: vi.fn(),
  };
});

import {
  getFutureCards,
  getFutureCardPredictions,
  getFutureFightOdds,
  getMyPredictions,
  getUserCardLeaderboard,
  savePrediction,
} from "../api/client.js";

function renderView() {
  return render(
    <AppContext.Provider
      value={{
        imageLookup: {},
        openProfile: () => {},
        routeParam: "",
        reflectRoute: () => {},
      }}
    >
      <MyPicks />
    </AppContext.Provider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  getFutureCards.mockResolvedValue([CARD]);
  getFutureCardPredictions.mockResolvedValue(DETAIL);
  getFutureFightOdds.mockResolvedValue([]);
  getMyPredictions.mockResolvedValue([]);
  getUserCardLeaderboard.mockResolvedValue([
    { rank: 1, display_name: "Ada", user_id: 1, rating: 1042, wins: 3, losses: 1, graded: 4, accuracy: 0.75, is_me: false, method_picks: 0 },
  ]);
  savePrediction.mockImplementation(async (fightUrl, fighter, method) => ({
    fight_url: fightUrl,
    picked_fighter: fighter,
    picked_method: method,
    event_id: CARD.event_id,
    status: "pending",
    locked: false,
  }));
  try {
    localStorage.setItem("fightiq_intro_seen", "1");
  } catch {
    /* jsdom without storage */
  }
});

test("queue strip summarizes open cards; standings only fetch on tab open", async () => {
  const user = userEvent.setup();
  renderView();

  expect(await screen.findByText("Ada Striker")).toBeInTheDocument();
  expect(screen.getByText(/open card/)).toBeInTheDocument();
  expect(screen.getByText(/pick(s)? needed/)).toBeInTheDocument();

  // lazy standings: no fetch until the tab is opened
  expect(getUserCardLeaderboard).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Standings" }));
  await waitFor(() => expect(getUserCardLeaderboard).toHaveBeenCalledTimes(1));
  expect(await screen.findByText("Ada")).toBeInTheDocument();

  // fights come back
  await user.click(screen.getByRole("button", { name: "Fights" }));
  expect(await screen.findByText("Ada Striker")).toBeInTheDocument();
});

test("tapping a fighter saves a winner pick", async () => {
  const user = userEvent.setup();
  renderView();

  const option = await screen.findByRole("button", { name: "Pick Ada Striker to win" });
  await user.click(option);

  await waitFor(() =>
    expect(savePrediction).toHaveBeenCalledWith("http://fights/1", "Ada Striker", null)
  );
  await waitFor(() => expect(option.getAttribute("aria-pressed")).toBe("true"));
});
