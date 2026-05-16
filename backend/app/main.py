from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.prediction_service import (
    FighterNotFoundError,
    get_available_weight_classes,
    predict_fight_data,
    search_fighters,
)

from app.services.future_card_service import (
    get_future_card,
    get_future_card_predictions,
    get_future_cards,
    refresh_upcoming_cards,
)

from app.services.update_job_service import (
    get_latest_update_report,
    get_update_status,
    start_incremental_update_job,
)

from app.services.saved_prediction_service import (
    get_saved_card_predictions,
    save_predictions_for_all_future_cards,
    save_predictions_for_card,
)

from app.services.recent_card_service import (
    get_recent_card,
    get_recent_cards,
)

app = FastAPI(
    title="UFC Fight Predictor API",
    description="Predicts UFC fight winner probabilities using historical fight data.",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictionRequest(BaseModel):
    fighter_a: str
    fighter_b: str
    weight_class: str


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "UFC Fight Predictor API is running.",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
    }


@app.get("/fighters/search")
def fighter_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=25),
) -> dict[str, Any]:
    return {
        "query": query,
        "fighters": search_fighters(query=query, limit=limit),
    }


@app.get("/weight-classes")
def weight_classes() -> dict[str, list[str]]:
    return {
        "weight_classes": get_available_weight_classes(),
    }


@app.post("/predict")
def predict_fight(request: PredictionRequest) -> dict[str, Any]:
    try:
        return predict_fight_data(
            fighter_a=request.fighter_a,
            fighter_b=request.fighter_b,
            weight_class=request.weight_class,
        )

    except FighterNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Could not find fighter: {error.fighter_name}",
                "suggestions": error.suggestions,
            },
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Prediction failed.",
                "error": str(error),
            },
        )


@app.post("/future-cards/refresh")
def refresh_future_cards() -> dict[str, Any]:
    try:
        result = refresh_upcoming_cards()

        return {
            "message": "Future cards refreshed.",
            **result,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to refresh future cards.",
                "error": str(error),
            },
        )


@app.get("/future-cards")
def future_cards() -> dict[str, Any]:
    try:
        return {
            "cards": get_future_cards(),
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to load future cards.",
                "error": str(error),
            },
        )


@app.get("/future-cards/{event_id}")
def future_card_detail(event_id: str) -> dict[str, Any]:
    try:
        return get_future_card(event_id)

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(error),
            },
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to load future card.",
                "error": str(error),
            },
        )


@app.get("/future-cards/{event_id}/predictions")
def future_card_predictions(event_id: str) -> dict[str, Any]:
    try:
        return get_future_card_predictions(event_id)

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(error),
            },
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to predict future card.",
                "error": str(error),
            },
        )
    
@app.post("/admin/update/start")
def start_update() -> dict[str, Any]:
    return start_incremental_update_job()


@app.get("/admin/update/status")
def update_status() -> dict[str, Any]:
    return get_update_status()


@app.get("/admin/update/latest-report")
def latest_update_report() -> dict[str, Any]:
    return get_latest_update_report()

@app.post("/future-cards/{event_id}/save-predictions")
def save_future_card_predictions(event_id: str) -> dict[str, Any]:
    try:
        return save_predictions_for_card(event_id)

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(error),
            },
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to save future-card predictions.",
                "error": str(error),
            },
        )


@app.post("/future-cards/save-all-predictions")
def save_all_future_card_predictions() -> dict[str, Any]:
    try:
        return save_predictions_for_all_future_cards()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to save all future-card predictions.",
                "error": str(error),
            },
        )


@app.get("/saved-card-predictions")
def saved_card_predictions() -> dict[str, Any]:
    try:
        return get_saved_card_predictions()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to load saved card predictions.",
                "error": str(error),
            },
        )
    
@app.get("/recent-cards")
def recent_cards(
    include_waiting: bool = True,
) -> dict[str, Any]:
    try:
        return get_recent_cards(include_waiting=include_waiting)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to load recent cards.",
                "error": str(error),
            },
        )


@app.get("/recent-cards/{event_id}")
def recent_card_detail(event_id: str) -> dict[str, Any]:
    try:
        return get_recent_card(event_id)

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(error),
            },
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to load recent card.",
                "error": str(error),
            },
        )