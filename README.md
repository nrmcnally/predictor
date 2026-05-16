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
