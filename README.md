# UFC Fight Predictor

A full-stack UFC fight prediction app that uses scraped UFCStats data, fighter history, Elo-style ratings, physical profile data, and a calibrated machine-learning model to predict individual fights and upcoming UFC cards.

## Features

- Single-fight win probability predictions
- Upcoming card predictions
- Recent card tracking using saved pre-fight predictions
- Incremental update pipeline
- Model retraining
- Fighter search
- Confidence labels
- “Why this prediction?” explanation panel

## Tech Stack

Backend:

- Python
- FastAPI
- pandas
- scikit-learn
- XGBoost
- BeautifulSoup
- Uvicorn

Frontend:

- React
- Vite
- CSS

## How to Run

Open two terminals.

### Terminal 1: Backend

```cmd
cd C:\Users\nrmcn\Desktop\ufc-predictor\backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Backend docs:

```text
http://127.0.0.1:8000/docs
```

### Terminal 2: Frontend

```cmd
cd C:\Users\nrmcn\Desktop\ufc-predictor\frontend
npm run dev
```

Frontend:

```text
http://localhost:5173/
```

## Updating Data

Use the **Update data** tab in the app.

This runs the incremental update pipeline:

1. Refresh completed events
2. Add newly completed fights
3. Scrape only missing fight details
4. Rebuild features
5. Retrain the calibrated model
6. Rebuild current fighter data
7. Refresh future cards
8. Save future-card prediction snapshots

Command-line version:

```cmd
cd C:\Users\nrmcn\Desktop\ufc-predictor\backend
.venv\Scripts\activate
python -m app.pipeline.update_incremental_data
```

## Main Project Structure

```text
ufc-predictor/
├── backend/
│   ├── app/
│   │   ├── data/       # scrapers
│   │   ├── features/   # feature engineering
│   │   ├── models/     # model training and CLI prediction
│   │   ├── pipeline/   # update pipelines
│   │   ├── services/   # backend app logic
│   │   └── main.py     # FastAPI app
│   ├── data/
│   └── models/
├── frontend/
│   └── src/
└── README.md
```

## Important Notes

The normal update path is incremental. Do not use the full rebuild unless scraper or feature logic changes, because it can take a long time.

The app intentionally avoids fallback predictions for fighters with missing data. If there is not enough historical data, the app shows “No prediction” instead of making a weak prediction.

Saved future-card predictions are used later by the Recent Cards tab to compare pre-fight predictions against actual results.

## Troubleshooting

If the backend virtual environment is not active:

```cmd
cd C:\Users\nrmcn\Desktop\ufc-predictor\backend
.venv\Scripts\activate
```

If the backend fails after editing Python files:

```cmd
python -m py_compile app\services\prediction_service.py
```

If the frontend does not update:

```cmd
Ctrl + C
npm run dev
```

## Roadmap

Possible future improvements:

- Method-of-victory prediction
- Model evaluation/backtesting screen
- Export card predictions
- UI polish
- Deployment packaging

NEW SET UP

---

# Setting Up on a New Machine

This project does **not** include local virtual environments, Node dependencies, scraped data files, or trained model files in Git.

That means after cloning the repo on a new machine, you need to recreate the backend/frontend dependencies and either copy or rebuild the data/model files.

## 1. Clone the Repository

From the folder where you want the project:

```cmd
git clone https://github.com/YOUR_USERNAME/ufc-predictor.git
cd ufc-predictor
```

Check that Git is connected:

```cmd
git status
git remote -v
```

## 2. Set Up the Backend Virtual Environment

Go into the backend folder:

```cmd
cd backend
```

Create a new virtual environment:

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

## 3. Install Backend Dependencies

If the project has a `requirements.txt` file:

```cmd
pip install -r requirements.txt
```

If there is no `requirements.txt` yet, install the main packages manually:

```cmd
pip install fastapi uvicorn pandas scikit-learn xgboost beautifulsoup4 requests joblib python-multipart
```

## 4. Set Up the Frontend

Open a second terminal and go to the frontend folder:

```cmd
cd C:\path\to\ufc-predictor\frontend
```

Install Node dependencies:

```cmd
npm install
```

## 5. Restore Data and Model Files

The following folders/files are usually ignored by Git:

```text
backend/data/raw/*.csv
backend/data/processed/*.csv
backend/models/*.joblib
backend/models/*.json
```

Because of that, a freshly cloned machine may not be able to make predictions right away.

You have two options.

### Option A: Copy Data From the Original Machine

From the original machine, copy these folders into the same location on the new machine:

```text
backend/data/
backend/models/
```

This is the fastest way to make the app work exactly like it did before.

### Option B: Rebuild Data and Model Files

From the backend folder with `.venv` activated:

```cmd
python -m app.pipeline.update_incremental_data
```

If the project has no existing data files at all, the incremental update may not be enough. In that case, run the full rebuild:

```cmd
python -m app.pipeline.update_all_data
```

Warning: the full rebuild can take a long time because it may scrape every historical fight-detail page.

## 6. Run the Backend

In the backend terminal:

```cmd
cd C:\path\to\ufc-predictor\backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Backend docs:

```text
http://127.0.0.1:8000/docs
```

## 7. Run the Frontend

In the frontend terminal:

```cmd
cd C:\path\to\ufc-predictor\frontend
npm run dev
```

Frontend:

```text
http://localhost:5173/
```

## 8. Optional: Use the Launcher

If `start_app.bat` exists in the project root, you can double-click it after setup.

It expects:

```text
backend/.venv/
frontend/node_modules/
```

to already exist.

If either one is missing, set up the backend and frontend first using the steps above.

## Common New-Machine Issues

### `.venv` cannot be found

This is normal after cloning. Create it again:

```cmd
cd C:\path\to\ufc-predictor\backend
python -m venv .venv
.venv\Scripts\activate
```

### `node_modules` cannot be found

This is normal after cloning. Reinstall frontend dependencies:

```cmd
cd C:\path\to\ufc-predictor\frontend
npm install
```

### Backend starts but predictions fail

The model or data files are probably missing.

Check for:

```text
backend/models/best_winner_model.joblib
backend/models/model_features.json
backend/data/processed/current_fighter_features.csv
```

Copy `backend/data` and `backend/models` from the original machine, or rebuild them with the update pipeline.

### Frontend loads but cannot reach API

Make sure the backend is running at:

```text
http://127.0.0.1:8000
```

and the frontend is running at:

```text
http://localhost:5173
```
