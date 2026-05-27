# UFC Fight Predictor

A full-stack UFC fight prediction app that uses scraped UFCStats data, fighter history, Elo-style ratings, physical profile data, age features, calibrated machine-learning models, and optional betting-odds comparison data to predict individual fights and upcoming UFC cards.

The app includes a FastAPI backend, a React/Vite frontend, an incremental data update pipeline, future-card predictions, saved pre-fight prediction tracking, optional market-odds snapshots, fighter profile pages with photos and Elo trends, leaderboards, model evaluation tools, and a rule-based “Why this prediction?” explanation panel.

---

## Features

- Single-fight winner prediction with calibrated win probabilities
- Manner-of-ending prediction for single fights
  - Broad method probabilities: Decision, KO/TKO, Submission, Other
  - Detailed method probabilities such as unanimous decision, punch-based KO/TKO, choke submission, split/majority decision, and more
- “Why this prediction?” matchup insight panel
- Basic matchup edge comparison
  - Elo
  - Experience
  - Win rate
  - Reach
  - Height
  - Striking differential
  - Takedown differential
  - Age / career-stage edge
- Future Cards tab with known upcoming UFC cards and winner predictions
- Optional betting-odds comparison for future fights
  - Shows current American odds when available
  - Shows no-vig market-implied probabilities
  - Compares model pick vs. market favorite
- Recent Cards tab that compares saved pre-fight predictions against actual results
  - Saves odds snapshots with pre-fight predictions when `ODDS_API_KEY` is configured
  - Later compares model pick vs. market favorite vs. actual winner
- Fighter Profile tab
  - Fighter photo or initials fallback
  - Current Elo, peak Elo, UFC record, win rate, age, height, and reach
  - Recent form summary
  - Elo/form trend graph
  - Style assumptions based on available striking, grappling, and defense features
  - Notable top-10 rankings overall or by weight class when available
  - Recent fight history with clickable opponent navigation
- Fighter images in Single Fight, Future Cards, Recent Cards, Leaderboards, and Fighter Profile views
- Clickable fighter names in navigation-oriented areas to open Fighter Profile pages
- Leaderboards by overall ranking and weight class
- Model Evaluation tab
  - Fight accuracy
  - Brier score
  - Log loss
  - ROC AUC
  - Confidence bucket calibration
  - Favorite-threshold performance
  - Most confident correct and wrong predictions
  - Method model metrics
- Incremental update pipeline
- Model retraining from the UI or command line
- DOB restore / backup support for age features
- Fighter search
- Confidence labels
- Optional local launcher with `start_app.bat`

---

## Tech Stack

### Backend

- Python
- FastAPI
- pandas
- scikit-learn
- XGBoost
- BeautifulSoup
- requests
- joblib
- Uvicorn
- Playwright, used as a fallback when UFCStats returns a browser-check page

### Frontend

- React
- Vite
- CSS

---

# Setup

## 1. Clone the Repository

```cmd
git clone https://github.com/nrmcnally/predictor.git
cd predictor
```

Check that Git is connected:

```cmd
git status
git remote -v
```

---

## 2. Set Up the Backend

Go into the backend folder:

```cmd
cd backend
```

Create a Python virtual environment:

```cmd
python -m venv .venv
```

Activate it:

```cmd
.venv\Scripts\activate
```

Your terminal should now show:

```text
(.venv)
```

Install backend dependencies:

```cmd
pip install -r requirements.txt
```

If `requirements.txt` is missing, install the main packages manually:

```cmd
pip install fastapi uvicorn pandas scikit-learn xgboost beautifulsoup4 requests joblib python-multipart playwright
```

Install the Playwright Chromium browser dependency:

```cmd
python -m playwright install chromium
```

This is required because UFCStats may return a JavaScript/browser-check page to normal `requests` calls. The scraper tries `requests` first, then uses Playwright as a fallback when needed.

---

## 3. Set Up the Frontend

Open a second terminal from the project root and run:

```cmd
cd frontend
npm install
```

---
## 4. Optional: Set Up Betting Odds Comparison

Betting odds are optional. The app does **not** use betting odds as model training features. Odds are only shown as comparison data next to the model prediction.

The odds feature currently uses [The Odds API](https://the-odds-api.com/) for current/upcoming MMA odds.

### Get an API Key

1. Create an account at The Odds API.
2. Copy your API key from your account dashboard.
3. Store it locally as an environment variable.

### Temporary Current-Terminal Setup

From a backend terminal:

```cmd
set ODDS_API_KEY=your_api_key_here
```

This only applies to the current terminal window.

### Permanent Windows Setup

```cmd
setx ODDS_API_KEY "your_api_key_here"
```

After using `setx`, close and reopen your terminal before running the app.

### Local Launcher Option

Do **not** put your real API key in `start_app.bat` if that file is committed to Git.

Instead, create a private local launcher named:

```text
start_app.local.bat
```

Add this file to `.gitignore`:

```text
/start_app.local.bat
```

Then create `start_app.local.bat` in the project root:

```bat
@echo off
set "ODDS_API_KEY=your_api_key_here"

start "UFC Predictor Backend" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate && uvicorn app.main:app --reload"
start "UFC Predictor Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
```

Double-click `start_app.local.bat` to run the app with the API key loaded into the backend process.

Never commit `start_app.local.bat`, `.env`, or any file containing your real API key.

---

# Running the App

You need two terminals open.

## Terminal 1: Backend

From the project root:

```cmd
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Backend API docs:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Terminal 2: Frontend

From the project root:

```cmd
cd frontend
npm run dev
```

Frontend:

```text
http://localhost:5173/
```

---

# Optional: Use a Local Launcher

If `start_app.bat` exists in the project root, you can double-click it after setup.

It expects these to already exist:

```text
backend/.venv/
frontend/node_modules/
```

If either one is missing, complete the backend and frontend setup steps first.

If you use betting odds, prefer a private `start_app.local.bat` file instead of putting your real API key in a committed launcher. See **Optional: Set Up Betting Odds Comparison** above.

---

# Data and Model Files

This project does **not** include local virtual environments, Node dependencies, scraped CSV data, or trained model files in Git.

These files are usually ignored:

```text
backend/data/raw/*.csv
backend/data/processed/*.csv
backend/data/reports/*.csv
backend/data/reports/*.json
backend/data/raw/current_mma_odds.json
backend/data/raw/fighter_images.csv
backend/data/processed/future_fight_odds.csv
backend/models/*.joblib
backend/models/*.json
backend/.venv/
frontend/node_modules/
start_app.local.bat
.env
backend/.env
frontend/.env
```

Because of that, a freshly cloned machine may not be able to make predictions immediately.

You have two options.

## Option A: Copy Data From Another Machine

From the original working machine, copy these folders into the same locations on the new machine:

```text
backend/data/
backend/models/
```

This is the fastest way to make the app work exactly like it did before.

## Option B: Rebuild Data and Model Files

From the backend folder with `.venv` activated:

```cmd
python -m app.pipeline.update_incremental_data
```

If the project has no existing data files at all, the incremental update may not be enough. In that case, run the full rebuild:

```cmd
python -m app.pipeline.update_all_data
```

Warning: the full rebuild can take a long time because it may scrape every historical fight-detail page.

---

# Expected Model Files

The backend expects trained model files in `backend/models/`, including:

```text
best_winner_model.joblib
model_features.json
calibrated_model_metrics.json
method_broad_model.joblib
method_detailed_model.joblib
method_model_features.json
method_model_metrics.json
```

The winner model powers fight winner predictions. The method models power the Single Fight “Manner of ending” panel.

---

# Updating Data

Use the **Update data** tab in the app.

The normal update path is incremental. It:

1. Refreshes completed events
2. Adds newly completed fights
3. Scrapes only missing fight details
4. Refreshes fighter profiles
5. Restores fighter DOBs from backup if needed
6. Rebuilds fighter snapshots
7. Adds Elo, physical, and age features
8. Rebuilds matchup training rows
9. Builds method labels and method training data
10. Retrains method/manner-of-ending models
11. Retrains the calibrated winner model
12. Rebuilds current fighter data
13. Adds current age features
14. Refreshes future cards
15. Refreshes future fight odds if `ODDS_API_KEY` is configured
16. Refreshes fighter image URLs for relevant future/current fighters when configured in the update script
17. Saves future-card prediction snapshots, including odds snapshots when available

Command-line version:

```cmd
cd backend
.venv\Scripts\activate
python -m app.pipeline.update_incremental_data
```

## Fighter Image Refresh

Fighter images are stored in:

```text
backend/data/raw/fighter_images.csv
```

The app uses this CSV as a local lookup file. If an image is missing, the frontend falls back to initials.

Refresh images for upcoming/saved-card fighters:

```cmd
cd backend
.venv\Scripts\activate
python -m app.data.scrape_fighter_images --mode future
```

Refresh images for the broader current fighter feature set:

```cmd
python -m app.data.scrape_fighter_images --mode current
```

Useful options:

```cmd
python -m app.data.scrape_fighter_images --mode current --limit 100
python -m app.data.scrape_fighter_images --mode future --force
```

Image scraping uses UFC.com athlete profile pages and their `og:image` metadata. Some fighters may need manual slug fixes when UFC.com uses a non-obvious athlete URL.

Do **not** use the full rebuild unless scraper or feature-generation logic changes.

---

# Main Project Structure

```text
predictor/
├── backend/
│   ├── app/
│   │   ├── analysis/   # analysis scripts, model evaluation helpers, category leaders
│   │   ├── data/       # scrapers and DOB restore tools
│   │   ├── features/   # feature engineering and training data builders
│   │   ├── models/     # model training and CLI prediction scripts
│   │   ├── pipeline/   # update pipelines
│   │   ├── services/   # backend app logic
│   │   └── main.py     # FastAPI app
│   ├── data/
│   │   ├── raw/
│   │   ├── processed/
│   │   └── reports/
│   └── models/
├── frontend/
│   ├── src/
│   └── package.json
├── start_app.bat
└── README.md
```

---

# App Tabs

## Single Fight

Predicts the winner and win probabilities for one matchup.

Includes:

- Predicted winner
- Confidence label
- Win percentages
- “Why this prediction?” explanation
- Basic matchup edges
- Manner-of-ending probabilities
  - Broad method breakdown
  - Detailed method breakdown

Method prediction is intentionally separate from winner prediction. It should be treated as directional fight-ending context, not a guaranteed exact finish prediction.

## Fighter Profile

Shows a fighter-level scouting page.

Includes:

- Fighter photo or initials fallback
- Current Elo and peak Elo
- UFC record and win rate
- Age, height, and reach when available
- Recent form summary
- Elo/form trend graph
- Style profile based on available striking, grappling, and defensive statistics
- Notable top-10 rankings overall or within weight class when available
- Method tendencies
- Stat snapshot
- Recent fight history

Opponents in the recent fight history can be clicked to load that opponent’s Fighter Profile.

Some style labels and notable rankings are heuristic, data-derived summaries. They are not official UFC labels and should be treated as directional scouting context.

## Future Cards

Shows upcoming UFC cards and predicted winners for scheduled fights.

Includes:

- Card summary stats
- Prediction availability count
- Confidence badges
- Winner predictions for known fights
- Optional current betting odds when `ODDS_API_KEY` is configured
- No-vig market-implied probabilities
- Model pick vs. market favorite comparison

Some fights may show:

```text
No prediction
```

This usually means one or both fighters are missing from the historical feature data.

Method predictions are not shown here because they are less accurate and would make card-level predictions too noisy.

## Recent Cards

Compares saved pre-fight predictions against actual fight results once the event has completed and the data has been updated.

Includes:

- Saved predictions
- Saved market odds snapshots when available
- Actual winners after results are scraped
- Correct / wrong / waiting status
- Card-level model accuracy summary
- Market favorite accuracy summary when odds were saved before the event

A card may show:

```text
Waiting for results
```

until the event happens and the update pipeline has scraped the completed results.

## Leaderboards

Shows best and worst fighters by category.

Leaderboards can be viewed:

- Overall
- By weight class

Categories include things like overall score, striking, grappling, wrestling, finishing, defense, Elo, experience, reach, and reach-for-size.

## Evaluation

Shows model performance and backtesting information.

Includes:

- Fight accuracy
- Brier score
- Log loss
- ROC AUC
- Confidence bucket calibration
- Favorite-threshold performance
- Performance by weight class
- Performance by year
- Most confident correct picks
- Most confident wrong picks
- Broad and detailed method model metrics

Historical betting-odds evaluation is only available for fights where odds were saved locally before the event. The app does not currently include paid historical odds data.

## Update Data

Runs the incremental update pipeline from the UI and shows progress.

The update can take several minutes if new fights need to be scraped or models need to be retrained.

---

# Important Notes

The app intentionally avoids fallback predictions for fighters with missing data.

If there is not enough historical data, the app shows:

```text
No prediction
```

instead of making a weaker low-quality prediction.

The “Why this prediction?” panel is rule-based. It does not claim to be the exact internal reasoning of the machine-learning model. It explains the matchup using the same pre-fight edge data returned by the backend.

The method/manner-of-ending model is less accurate than the winner model. It is currently shown only in the Single Fight view to avoid cluttering Future Cards and Recent Cards.

Betting odds are comparison-only data. They are not used as model features and are not used to train the winner model or method model.

Recent Cards can only compare against market odds when those odds were saved before the event. If odds were not available or the API key was not configured when the snapshot was saved, the card will show market odds as unavailable.

---

# Useful Commands

## Run Backend

```cmd
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

## Run Frontend

```cmd
cd frontend
npm run dev
```

## Run Incremental Update

```cmd
cd backend
.venv\Scripts\activate
python -m app.pipeline.update_incremental_data
```

## Refresh Future Fight Odds

Requires `ODDS_API_KEY` to be set.

```cmd
cd backend
.venv\Scripts\activate
python -m app.services.odds_service
```

## Refresh Fighter Images

Future/saved-card fighters:

```cmd
cd backend
.venv\Scripts\activate
python -m app.data.scrape_fighter_images --mode future
```

Current fighter feature set:

```cmd
python -m app.data.scrape_fighter_images --mode current
```

## Run Full Rebuild

```cmd
cd backend
.venv\Scripts\activate
python -m app.pipeline.update_all_data
```

## Train Calibrated Winner Model

```cmd
cd backend
.venv\Scripts\activate
python -m app.models.train_calibrated_models
```

## Build Method Training Data

```cmd
cd backend
.venv\Scripts\activate
python -m app.analysis.explore_method_labels
python -m app.features.build_method_training_data
```

## Train Method Models

```cmd
cd backend
.venv\Scripts\activate
python -m app.models.train_method_models
```

## Add Age Features

```cmd
cd backend
.venv\Scripts\activate
python -m app.features.add_age_features
```

## Restore Fighter DOBs From Backup

```cmd
cd backend
.venv\Scripts\activate
python -m app.data.restore_fighter_dobs
```

## Predict One Fight From CLI

```cmd
cd backend
.venv\Scripts\activate
python -m app.models.predict_fight --fighter-a "Khamzat Chimaev" --fighter-b "Sean Strickland" --weight-class "Middleweight"
```

## Run Category Leader Analysis

```cmd
cd backend
.venv\Scripts\activate
python -m app.analysis.category_leaders
```

Example with looser filters:

```cmd
python -m app.analysis.category_leaders --top 5 --min-fights 3
```

---

# Troubleshooting

## `.venv` Cannot Be Found

This is normal after cloning because `.venv` is not committed to Git.

Create it again:

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
```

## `node_modules` Cannot Be Found

This is normal after cloning because `node_modules` is not committed to Git.

Reinstall frontend dependencies:

```cmd
cd frontend
npm install
```

## UFCStats Scraping Returns `Loading…` or `Checking your browser…`

UFCStats may serve a browser-check page to normal `requests` calls. The scraper now uses Playwright as a fallback, but Playwright must be installed in the active backend environment.

From the backend folder:

```cmd
.venv\Scripts\activate
pip install playwright
python -m playwright install chromium
```

Quick diagnostic:

```cmd
python -c "from bs4 import BeautifulSoup; from app.data.ufcstats_fetcher import fetch_ufcstats_html,is_browser_check_html; html=fetch_ufcstats_html('http://ufcstats.com/statistics/events/completed?page=all'); soup=BeautifulSoup(html,'html.parser'); print('browser_check:',is_browser_check_html(html)); print('title:',soup.title.get_text(' ',strip=True) if soup.title else 'NO TITLE'); print('event links:',len(soup.select('a[href*=\"/event-details/\"]')))"
```

A healthy response should show `browser_check: False`, title `Stats | UFC`, and hundreds of event links.

## Backend Starts but Predictions Fail

The model or data files are probably missing.

Check for:

```text
backend/models/best_winner_model.joblib
backend/models/model_features.json
backend/models/method_broad_model.joblib
backend/models/method_detailed_model.joblib
backend/models/method_model_features.json
backend/data/processed/current_fighter_features.csv
```

Copy `backend/data` and `backend/models` from a working machine, or rebuild them with the update pipeline.

## Age Edge Is Missing

Check that the DOB and age files exist and have values:

```cmd
cd backend
.venv\Scripts\activate
python -c "import pandas as pd; df=pd.read_csv('data/raw/fighter_profiles.csv'); print(df[['dob_raw','dob']].notna().sum())"
python -c "import pandas as pd; df=pd.read_csv('data/processed/current_fighter_features.csv'); print([c for c in df.columns if 'age' in c.lower()])"
```

If DOBs were wiped, restore them:

```cmd
python -m app.data.restore_fighter_dobs
python -m app.features.add_age_features
```

## Method Prediction Is Missing

Check for:

```text
backend/models/method_broad_model.joblib
backend/models/method_detailed_model.joblib
backend/models/method_model_features.json
```

If needed, rebuild method data and models:

```cmd
python -m app.analysis.explore_method_labels
python -m app.features.build_method_training_data
python -m app.models.train_method_models
```

## Betting Odds Are Missing

Odds are optional. First check that your API key is available in the backend terminal:

```cmd
echo %ODDS_API_KEY%
```

If it prints nothing, set it for the current terminal:

```cmd
set ODDS_API_KEY=your_api_key_here
```

Then refresh odds:

```cmd
cd backend
.venv\Scripts\activate
python -m app.services.odds_service
```

Expected generated files:

```text
backend/data/raw/current_mma_odds.json
backend/data/raw/fighter_images.csv
backend/data/processed/future_fight_odds.csv
```

These generated files should stay ignored by Git.

If Future Cards shows odds but Recent Cards does not, that usually means the card was saved before odds were added. Run the incremental update again before the event to save a new snapshot that includes odds.

## Fighter Images Are Missing

Fighter images are optional. Missing images fall back to initials.

Check whether the image CSV exists:

```cmd
cd backend
.venv\Scripts\activate
python -c "import pandas as pd; df=pd.read_csv('data/raw/fighter_images.csv'); print(df.shape); print(df.head().to_string())"
```

Refresh images:

```cmd
python -m app.data.scrape_fighter_images --mode future
python -m app.data.scrape_fighter_images --mode current
```

If one fighter is missing, UFC.com may use an unusual athlete slug. You can manually add a row to `backend/data/raw/fighter_images.csv` with:

```text
fighter,image_url,source_url,slug,page_title
```

## Fighter Profile Tab Does Not Load

Check that the backend is running and the endpoint responds:

```cmd
cd backend
.venv\Scripts\activate
python -c "import requests; r=requests.get('http://127.0.0.1:8000/fighter-profile', params={'fighter':'Khamzat Chimaev'}); print(r.status_code); print(r.text[:500])"
```

If this fails, verify that `backend/data/processed/current_fighter_features.csv`, `backend/data/raw/fight_stats.csv`, and the trained model/data pipeline outputs exist.

## Frontend Loads but Cannot Reach API

Make sure the backend is running at:

```text
http://127.0.0.1:8000
```

and the frontend is running at:

```text
http://localhost:5173
```

---

# Roadmap

Possible future improvements:

- Weight-class movement and size-context features
- Export card predictions
- Deployment packaging
- More detailed model diagnostics
- Fighter comparison mode
- Better profile charts and tooltips
- Model-vs-market evaluation for saved odds snapshots
- Better handling for fighters with limited UFC history
