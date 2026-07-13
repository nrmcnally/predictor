# Reading the Tea Leaves — a user's guide to FIGHT IQ predictions

_For everyone in the crew who looks at "ASPINALL 64%" and wants to know what it
actually means, where it came from, and when to ignore it. Written 2026-07-13,
against model v1.2. Numbers cited here come from the model's own held-out test
set (1,718 fights, 2023–2026) and the live prospective tracking._

---

## 1. What the number is

When FIGHT IQ says a fighter is **64%**, it is claiming: *in fights that look
statistically like this one, the fighter on this side of the matchup wins about
64 times out of 100.* It is a **probability**, not a verdict. A 64% favorite
loses more than one time in three — that is not the model being wrong, that is
what 64% means. The model is "wrong" only if its 64%-ers don't win about 64% of
the time over many fights.

That property — probabilities meaning what they say — is called **calibration**,
and it's the thing the app optimizes hardest. On the held-out test set the
buckets land close to honest:

| Model says | Fights | Actually won |
|---|---|---|
| 50–55% | 874 | 53% |
| 55–60% | 850 | 63% |
| 60–65% | 642 | 64% |
| 65–70% | 510 | 66% |
| 70–75% | 298 | 72% |
| 75%+ | 262 | ~81% |

So the headline probability is trustworthy *as a probability*. What it is not
is a promise about any single fight.

## 2. Where the number comes from

The short version of the pipeline:

1. **History.** Every UFC fight since 1994 is scraped from UFCStats — results,
   methods, and the full stat lines (strikes by target and position, takedowns,
   control time, knockdowns), plus fighter profiles (height, reach, stance,
   date of birth).
2. **Pre-fight snapshots.** For each fighter, at the moment of each fight, the
   pipeline computes ~110 features using **only what was knowable before that
   fight**: record and finish rates (with Bayesian shrinkage so a 2-fight
   sample doesn't scream), striking/grappling volume per 15 minutes, recent
   form over the last 3–5 fights, recency-decayed versions of everything,
   opponent-adjusted output (how much more did they land than that opponent
   usually allows), an Elo rating with method-aware K-factor, strength of
   schedule, physical attributes, age, layoff time, and fight context
   (5-rounder? main event?).
3. **The matchup.** The model sees the **difference** between the two fighters
   on every feature — it thinks in gaps, not absolutes.
4. **The model.** Five model types are trained and probability-calibrated;
   the one with the best probability quality on unseen fights wins the job.
   Currently that is a calibrated **logistic regression** — boring, honest,
   and hard to beat at this data size. Both orientations (A-vs-B and B-vs-A)
   are predicted and averaged so the ordering of names can't sway it.
5. **The split is chronological.** The model is always tested on fights that
   happened *after* everything it trained on — no peeking at the future.

What the model deliberately does **not** see: betting odds (predictions are
market-blind by design, so you can compare the two honestly), anything from
outside the UFC (a debutant's 20-0 regional record is invisible), and anything
that isn't in a stat line (injuries, camp changes, short-notice, weight-cut
misery, personal turmoil).

## 3. The labels, decoded

**Confidence labels** are fixed bands on the favorite's probability:

| Label | Probability |
|---|---|
| Very close / low confidence | < 55% |
| Slight lean | 55–60% |
| Moderate lean | 60–65% |
| Strong lean | 65–70% |
| High confidence | ≥ 70% |

Note the honest framing: at 55–60% the model itself is telling you it barely
leans. Treat "Slight lean" as a coin toss with a thumb on the scale.

**Data reliability** is about the *inputs*, not the output: it keys on the less
experienced fighter's UFC fight count. ≤1 prior UFC fight → "Very limited
data"; <5 → "Limited"; ≥5 → "Sufficient". A confident number on very limited
data is a red flag, and the app flags exactly that combination (≥75% confidence
with <5 fights of data) as high risk.

**Risk flags** you'll see on fights: long layoff (18+ months = medium, 3+ years
= high), a 10+ lb weight-class move, and the low-sample flags above. When the
overall risk is high, the percentage is resting on thin evidence — the model
can't know what it hasn't seen.

## 4. When to trust it less

Ranked roughly by how much they should discount your trust:

1. **Debuts and short samples.** The single biggest blind spot. A UFC debutant
   has *no* UFC history — the model is running on physical stats, age, and
   priors. Whatever the number says, mentally widen it toward 50%.
2. **Long layoffs.** The model knows days-since-last-fight, but a stat line
   from 2022 describes the 2022 fighter.
3. **Anything the stats can't see.** Short-notice replacements, camp changes,
   injuries carried into the fight, bad weight cuts. The model has no idea.
   If you know something it can't, this is exactly where a human should
   overrule it.
4. **Heavyweights and low-volume finishers.** One punch flips outcomes that
   the stat gaps said were leaning the other way. The model's variance is
   simply higher here (the round O/U line agrees — heavyweight fights rarely
   go long).
5. **Numbers in the 50–58% band.** These are honest near-coin-flips. The model
   saying 54% is information about *how close it is*, not a pick to lean on.
6. **Five-round main events between well-matched fighters.** Twenty-five
   minutes gives cardio and durability more say than any pre-fight stat line
   fully captures.

## 5. The market comparison, and how to use it

Every fight shows the model's number next to the betting market's (de-vigged
implied probability, averaged across books). Three things to know:

1. **The market is the strongest predictor in combat sports** — this is one of
   the most replicated findings in sports-prediction research. Expect the
   market to be right more often than the model; over the first tracked cards
   it has been (that's normal, not a bug).
2. **The interesting fights are the disagreements.** When model and market
   agree on the favorite, the model is telling you nothing the odds didn't.
   When they split, someone is wrong — that's where the model earns or loses
   its keep, and the Card results → Model record tab tracks exactly this
   ("Where we disagree with the market").
3. **Grades are Brier-based** (probability quality, not just hit rate):
   A ≈ market-sharp (~0.20), C ≈ coin-flip territory (~0.25). A single card's
   grade is noise — five fights can make anyone look like a genius or a bum.
   The overall grade across many cards is the real signal, which is why the
   app refuses to show verdicts until 10+ fights are graded.

**Model distance** on Future cards is a *different* model (the method model)
stating the probability the fight reaches the scorecards. Method prediction is
inherently noisier than winner prediction (top-1 method accuracy is ~53% —
against four options). Use it directionally: distance 30% means "expect
violence," not "under 2.5 locks."

## 6. Honest scoreboard (as of v1.2)

On 1,718 held-out fights the model never saw (2023–2026): **63.2% accuracy,
Brier 0.228** (the "decent independent model" band; the sharp market sits
around 0.20; coin-flipping is 0.25). Live prospective tracking since launch is
small-sample but consistent with those numbers. Published research and serious
practitioner models cluster in the same **60–68%** band, and the honest ceiling
for pre-fight MMA prediction appears to be roughly the market's own hit rate —
claims above ~70% have historically fallen apart under inspection. In other
words: the model is legitimate, the market is still sharper, and anyone
promising certainty in MMA is selling something.

## 7. Rules of thumb

- **Do** read 55% as "toss-up, tiny lean." **Don't** read it as a pick.
- **Do** downweight anything flagged limited-data or long-layoff.
- **Do** pay attention when the model and market disagree hard — and check
  the Model record tab later to see who was right.
- **Do** trust the *calibration*: over a season, the 70%-ers really do win
  about 70% of the time.
- **Don't** judge the model on one card. Brier grades over many cards are the
  only scoreboard that matters.
- **Don't** expect it to know about injuries, camps, short notice, or anyone's
  pre-UFC record. That's your job — it's why picking against the model is
  sometimes the smart move, and the app scores *you*, not it.
