# UFC Fight Predictor

A full-stack UFC fight prediction app that uses scraped UFCStats data, fighter history, Elo-style ratings, physical profile data, age features, and calibrated machine-learning models to predict individual fights and upcoming UFC cards.

The app includes a FastAPI backend, a React/Vite frontend, an incremental data update pipeline, future-card predictions, saved pre-fight prediction tracking, leaderboards, model evaluation tools, and a rule-based “Why this prediction?” explanation panel.

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
- Recent Cards tab that compares saved pre-fight predictions against actual results
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
pip install fastapi uvicorn pandas scikit-learn xgboost beautifulsoup4 requests joblib python-multipart
```

---

## 3. Set Up the Frontend

Open a second terminal from the project root and run:

```cmd
cd frontend
npm install
```

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

# Optional: Use the Local Launcher

If `start_app.bat` exists in the project root, you can double-click it after setup.

It expects these to already exist:

```text
backend/.venv/
frontend/node_modules/
```

If either one is missing, complete the backend and frontend setup steps first.

---

# Data and Model Files

This project does **not** include local virtual environments, Node dependencies, scraped CSV data, or trained model files in Git.

These files are usually ignored:

```text
backend/data/raw/*.csv
backend/data/processed/*.csv
backend/data/reports/*.csv
backend/data/reports/*.json
backend/models/*.joblib
backend/models/*.json
backend/.venv/
frontend/node_modules/
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
15. Saves future-card prediction snapshots

Command-line version:

```cmd
cd backend
.venv\Scripts\activate
python -m app.pipeline.update_incremental_data
```

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

## Future Cards

Shows upcoming UFC cards and predicted winners for scheduled fights.

Includes:

- Card summary stats
- Prediction availability count
- Confidence badges
- Winner predictions for known fights

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
- Actual winners after results are scraped
- Correct / wrong / waiting status
- Card-level accuracy summary

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
- Fighter profile pages
- Export card predictions
- Deployment packaging
- More detailed model diagnostics
- Better handling for fighters with limited UFC history
