# UFC Fight Predictor

A full-stack UFC fight prediction app that uses scraped UFCStats data, fighter history, Elo-style ratings, physical profile data, and a calibrated machine-learning model to predict individual fights and upcoming UFC cards.

The app includes a FastAPI backend, a React/Vite frontend, an incremental data update pipeline, future card predictions, saved pre-fight prediction tracking, and a rule-based “Why this prediction?” explanation panel.

## Features

- Single-fight win probability predictions
- Upcoming UFC card predictions
- Recent card tracking using saved pre-fight predictions
- Incremental update pipeline
- Model retraining
- Fighter search
- Confidence labels
- Basic matchup edge comparison
- “Why this prediction?” explanation panel
- Optional local launcher with `start_app.bat`

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

Install backend dependencies.

If the project has a `requirements.txt` file:

```cmd
pip install -r requirements.txt
```

If there is no `requirements.txt` yet, install the main packages manually:

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

# Updating Data

Use the **Update data** tab in the app.

The normal update path is incremental. It:

1. Refreshes completed events
2. Adds newly completed fights
3. Scrapes only missing fight details
4. Rebuilds fighter features
5. Retrains the calibrated model
6. Rebuilds current fighter data
7. Refreshes future cards
8. Saves future-card prediction snapshots

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
│   │   ├── analysis/   # fun analysis scripts, such as category leaders
│   │   ├── data/       # scrapers
│   │   ├── features/   # feature engineering
│   │   ├── models/     # model training and CLI prediction
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

## Future Cards

Shows upcoming UFC cards and predicted winners for scheduled fights.

Some fights may show:

```text
No prediction
```

This usually means one or both fighters are missing from the historical feature data.

## Recent Cards

Compares saved pre-fight predictions against actual fight results once the event has completed and the data has been updated.

A card may show:

```text
Waiting for results
```

until the event happens and the update pipeline has scraped the completed results.

## Update Data

Runs the incremental update pipeline from the UI and shows progress.

---

# Important Notes

The app intentionally avoids fallback predictions for fighters with missing data.

If there is not enough historical data, the app shows:

```text
No prediction
```

instead of making a weaker low-quality prediction.

The “Why this prediction?” panel is rule-based. It does not claim to be the exact internal reasoning of the machine-learning model. It explains the matchup using the same pre-fight edge data returned by the backend.

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

## Train Calibrated Model

```cmd
cd backend
.venv\Scripts\activate
python -m app.models.train_calibrated_models
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
backend/data/processed/current_fighter_features.csv
```

Copy `backend/data` and `backend/models` from a working machine, or rebuild them with the update pipeline.

## Frontend Loads but Cannot Reach API

Make sure the backend is running at:

```text
http://127.0.0.1:8000
```

and the frontend is running at:

```text
http://localhost:5173
```

## Backend Fails After Editing Python Files

Run a syntax check:

```cmd
cd backend
.venv\Scripts\activate
python -m py_compile app\services\prediction_service.py
```

If there is no output, the file syntax is okay.

Then restart the backend:

```cmd
uvicorn app.main:app --reload
```

## Frontend Does Not Update After Editing

Restart Vite:

```cmd
Ctrl + C
npm run dev
```

Then refresh the browser.

---

# Roadmap

Possible future improvements:

- Method-of-victory prediction
- Model evaluation/backtesting screen
- Export card predictions
- UI polish
- Deployment packaging