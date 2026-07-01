from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api_hardening import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    cors_origins,
)

import json
import logging
import os
from pathlib import Path

from app.services.method_prediction_service import predict_method_data

from app.services.fighter_image_service import (
    get_fighter_image_data,
    load_fighter_image_lookup,
)

from app.services.odds_service import (
    load_future_fight_odds,
    refresh_future_fight_odds,
)

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
    set_future_fight_scheduled_rounds,
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

from app.services.leaderboard_service import (
    get_leaderboard_options,
    get_leaderboards,
)

from app.services.model_evaluation_service import get_model_evaluation
from app.services.walk_forward_evaluation_service import run_walk_forward_evaluation

from app.services.fighter_profile_service import build_fighter_profile

from app.services.model_market_evaluation_service import build_model_market_evaluation
from app.services.model_snapshot_evaluation_service import build_model_snapshot_evaluation
from app.services.clv_evaluation_service import build_clv_evaluation
from app.services.data_quality_service import build_data_quality_summary

from app.auth.dependencies import get_current_user, require_admin
from app.services.auth_service import (
    authenticate,
    change_password,
    ensure_seed_admin,
    register_user,
    set_visibility,
    update_profile,
)
from app.repositories import users_repository
from app.db import connection
from app.services import (
    friends_compare_service,
    friends_service,
    predictions_service,
    predictions_scoring_service,
    predictions_stats_service,
)

app = FastAPI(
    title="UFC Fight Predictor API",
    description="Predicts UFC fight winner probabilities using historical fight data.",
    version="0.1.0",
)


# Middleware order: the LAST added is the OUTERMOST. CORS must be outermost so even
# rate-limited / errored responses carry CORS headers; rate limiting and security
# headers sit inside it.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("ufc_predictor")


@app.on_event("startup")
def _seed_admin_on_startup() -> None:
    # In demo mode, seed the isolated sandbox DB from prod before anything reads it.
    try:
        connection.ensure_demo_db()
    except Exception:
        logger.exception("Demo DB seed failed")
    if connection.is_demo():
        logger.warning("FIGHT IQ running in DEMO mode (sandbox DB: %s)", connection.get_db_path())
    # Create the bootstrap admin from ADMIN_EMAIL / ADMIN_PASSWORD when configured.
    try:
        ensure_seed_admin()
    except Exception:
        logger.exception("Admin seed failed")


# --- Centralized error handling -------------------------------------------------
# Endpoints stay thin: they call services and let domain exceptions bubble up to
# the handlers below. This removes the repetitive per-endpoint try/except blocks
# and guarantees consistent, non-leaky error responses.
#
# The 404 handlers keep the `{"detail": {...}}` envelope the frontend already
# parses (including fighter-name suggestions), so error display is unchanged.
# `FighterNotFoundError` subclasses `ValueError`, so its dedicated handler must be
# registered too — Starlette resolves to the most specific handler by MRO.


@app.exception_handler(FighterNotFoundError)
async def fighter_not_found_handler(
    request: Request, exc: FighterNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "detail": {
                "message": f"Could not find fighter: {exc.fighter_name}",
                "suggestions": exc.suggestions,
            }
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    # Services raise ValueError for "not found" / bad-identifier cases
    # (unknown event, card, or fighter). Surface the message at 404.
    return JSONResponse(
        status_code=404,
        content={"detail": {"message": str(exc)}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log full detail server-side; return a generic message so internal errors
    # (file paths, stack info) are never disclosed to clients.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"message": "Internal server error."})


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METHOD_MODEL_METRICS_PATH = PROJECT_ROOT / "models" / "method_model_metrics.json"


class FightPredictionRequest(BaseModel):
    fighter_a: str = Field(min_length=1, max_length=120)
    fighter_b: str = Field(min_length=1, max_length=120)
    weight_class: str = Field(min_length=1, max_length=60)


class ScheduledRoundsOverrideRequest(BaseModel):
    scheduled_rounds: int


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=60)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class RoleUpdateRequest(BaseModel):
    role: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class VisibilityRequest(BaseModel):
    is_public: bool


class ProfileUpdateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    display_name: str | None = Field(default=None, max_length=60)


class UserPredictionRequest(BaseModel):
    fight_url: str = Field(min_length=1, max_length=500)
    picked_fighter: str = Field(min_length=1, max_length=200)
    picked_method: str | None = Field(default=None, max_length=20)


class FriendRequestRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)


class FriendResponseRequest(BaseModel):
    accept: bool


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "UFC Fight Predictor API is running.",
    }


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "demo" if connection.is_demo() else "prod",
    }


# --- Auth: accounts, login, admin (Phase 2) -------------------------------------
# Auth endpoints translate ValueError to the correct status (400/401) themselves,
# instead of falling through to the generic ValueError->404 handler.


@app.post("/auth/register")
def auth_register(request: RegisterRequest) -> dict[str, Any]:
    try:
        user = register_user(request.email, request.password, request.display_name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"message": str(error)})
    return {"user": user}


@app.post("/auth/login")
def auth_login(request: LoginRequest) -> dict[str, Any]:
    try:
        return authenticate(request.email, request.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail={"message": str(error)})


@app.get("/auth/me")
def auth_me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": current_user}


@app.post("/auth/change-password")
def auth_change_password(
    request: ChangePasswordRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        change_password(current_user["id"], request.current_password, request.new_password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"message": str(error)})
    return {"message": "Password updated."}


@app.post("/auth/visibility")
def auth_set_visibility(
    request: VisibilityRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    set_visibility(current_user["id"], request.is_public)
    return {"is_public": request.is_public}


@app.post("/auth/profile")
def auth_update_profile(
    request: ProfileUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        user = update_profile(current_user["id"], request.email, request.display_name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"message": str(error)})
    return {"user": user}


# --- user predictions (account-based picks on upcoming fights) ----------------

@app.post("/predictions")
def create_prediction(
    request: UserPredictionRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        prediction = predictions_service.make_prediction(
            current_user["id"],
            request.fight_url,
            request.picked_fighter,
            request.picked_method,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"message": str(error)})
    return {"prediction": prediction}


@app.get("/predictions")
def list_predictions(
    event_id: str | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "predictions": predictions_service.list_predictions(current_user["id"], event_id)
    }


@app.delete("/predictions")
def delete_prediction(
    fight_url: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        removed = predictions_service.remove_prediction(current_user["id"], fight_url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"message": str(error)})
    return {"removed": removed}


@app.get("/predictions/stats")
def my_prediction_stats(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """The signed-in user's prediction record (accuracy primary) for the profile page."""
    return {"stats": predictions_stats_service.build_user_stats(current_user["id"])}


@app.post("/predictions/score", dependencies=[Depends(require_admin)])
def score_predictions() -> dict[str, Any]:
    """Grade all pending account picks against completed results (admin/batch)."""
    return predictions_scoring_service.score_all_pending()


@app.get("/leaderboard/users")
@app.get("/leaderboard/predictors", include_in_schema=False)
def user_leaderboard(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Public users ranked by FIGHT IQ rating (opt-in via profile visibility)."""
    return {
        "leaderboard": predictions_stats_service.build_leaderboard(current_user["id"])
    }


# --- friends (mutual-accept connections) --------------------------------------

@app.get("/friends")
def list_friends(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return friends_service.get_overview(current_user["id"])


@app.post("/friends/requests")
def send_friend_request(
    request: FriendRequestRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return friends_service.send_friend_request(current_user["id"], request.email)
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"message": str(error)})


@app.post("/friends/requests/{friendship_id}/respond")
def respond_friend_request(
    friendship_id: int,
    request: FriendResponseRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return friends_service.respond_to_request(
            current_user["id"], friendship_id, request.accept
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"message": str(error)})


@app.delete("/friends/{user_id}")
def remove_friend(
    user_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return {"removed": friends_service.remove_friend(current_user["id"], user_id)}


@app.get("/friends/{user_id}/compare")
def compare_with_friend(
    user_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return friends_compare_service.build_compare(current_user["id"], user_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"message": str(error)})


@app.get("/admin/users", dependencies=[Depends(require_admin)])
def admin_list_users() -> dict[str, Any]:
    return {"users": users_repository.list_users()}


@app.post("/admin/users/{user_id}/role", dependencies=[Depends(require_admin)])
def admin_set_user_role(user_id: int, request: RoleUpdateRequest) -> dict[str, Any]:
    if request.role not in {"user", "admin"}:
        raise HTTPException(
            status_code=400, detail={"message": "Role must be 'user' or 'admin'."}
        )
    if not users_repository.set_role(user_id, request.role):
        raise HTTPException(status_code=404, detail={"message": "User not found."})
    return {"user_id": user_id, "role": request.role}


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
def predict_fight(request: FightPredictionRequest) -> dict[str, Any]:
    return predict_fight_data(
        fighter_a=request.fighter_a,
        fighter_b=request.fighter_b,
        weight_class=request.weight_class,
    )


@app.post("/future-cards/refresh", dependencies=[Depends(require_admin)])
def refresh_future_cards() -> dict[str, Any]:
    return {
        "message": "Future cards refreshed.",
        **refresh_upcoming_cards(),
    }


@app.get("/future-cards")
def future_cards() -> dict[str, Any]:
    return {
        "cards": get_future_cards(),
    }


@app.get("/future-cards/{event_id}")
def future_card_detail(event_id: str) -> dict[str, Any]:
    return get_future_card(event_id)


@app.get("/future-cards/{event_id}/predictions")
def future_card_predictions(event_id: str) -> dict[str, Any]:
    return get_future_card_predictions(event_id)


@app.post(
    "/future-cards/{event_id}/fights/{fight_id}/scheduled-rounds",
    dependencies=[Depends(require_admin)],
)
def update_future_fight_scheduled_rounds(
    event_id: str,
    fight_id: str,
    request: ScheduledRoundsOverrideRequest,
) -> dict[str, Any]:
    return {
        "message": "Scheduled-rounds override saved.",
        **set_future_fight_scheduled_rounds(
            event_id=event_id,
            fight_id=fight_id,
            scheduled_rounds=request.scheduled_rounds,
        ),
    }


@app.post("/admin/update/start", dependencies=[Depends(require_admin)])
def start_update() -> dict[str, Any]:
    return start_incremental_update_job()


@app.get("/admin/update/status")
def update_status() -> dict[str, Any]:
    return get_update_status()


@app.get("/admin/update/latest-report")
def latest_update_report() -> dict[str, Any]:
    return get_latest_update_report()


@app.post("/future-cards/{event_id}/save-predictions", dependencies=[Depends(require_admin)])
def save_future_card_predictions(event_id: str) -> dict[str, Any]:
    return save_predictions_for_card(event_id)


@app.post("/future-cards/save-all-predictions", dependencies=[Depends(require_admin)])
def save_all_future_card_predictions() -> dict[str, Any]:
    return save_predictions_for_all_future_cards()


@app.get("/saved-card-predictions")
def saved_card_predictions() -> dict[str, Any]:
    return get_saved_card_predictions()


@app.get("/recent-cards")
def recent_cards(
    include_waiting: bool = True,
) -> dict[str, Any]:
    return get_recent_cards(include_waiting=include_waiting)


@app.get("/recent-cards/{event_id}")
def recent_card_detail(event_id: str) -> dict[str, Any]:
    return get_recent_card(event_id)


@app.get("/leaderboards/options")
def leaderboard_options() -> dict[str, Any]:
    return get_leaderboard_options()


@app.get("/leaderboards")
def leaderboards(
    top: int = 5,
    min_fights: int = 5,
    max_inactive_days: int = 1095,
) -> dict[str, Any]:
    return get_leaderboards(
        top=top,
        min_fights=min_fights,
        max_inactive_days=max_inactive_days,
    )


@app.get("/model-evaluation")
def model_evaluation(
    test_fraction: float = 0.20,
    recent_prediction_limit: int = 25,
) -> dict[str, Any]:
    return get_model_evaluation(
        test_fraction=test_fraction,
        recent_prediction_limit=recent_prediction_limit,
    )


@app.get("/walk-forward-evaluation")
def walk_forward_evaluation(
    n_folds: int = 8,
    min_test_fights: int = 150,
    min_train_fights: int = 1000,
) -> dict[str, Any]:
    return run_walk_forward_evaluation(
        n_folds=n_folds,
        min_test_fights=min_test_fights,
        min_train_fights=min_train_fights,
    )


@app.post("/predict-method")
def predict_method(request: FightPredictionRequest) -> dict[str, Any]:
    return predict_method_data(
        fighter_a=request.fighter_a,
        fighter_b=request.fighter_b,
        weight_class=request.weight_class,
    )


@app.get("/method-model-metrics")
def method_model_metrics() -> dict[str, Any]:
    if not METHOD_MODEL_METRICS_PATH.exists():
        return {
            "available": False,
            "message": "Method model metrics are not available yet. Train method models first.",
            "metrics": None,
        }

    with open(METHOD_MODEL_METRICS_PATH, "r", encoding="utf-8") as file:
        metrics = json.load(file)

    return {
        "available": True,
        "message": "Method model metrics loaded.",
        "metrics": metrics,
    }


@app.get("/future-fight-odds")
def future_fight_odds() -> dict[str, Any]:
    return load_future_fight_odds()


@app.post("/future-fight-odds/refresh", dependencies=[Depends(require_admin)])
def refresh_future_fight_odds_endpoint() -> dict[str, Any]:
    return refresh_future_fight_odds()


@app.get("/fighter-images")
def fighter_images() -> dict[str, Any]:
    image_lookup = load_fighter_image_lookup()

    return {
        "available": True,
        "count": len(image_lookup),
        "images": list(image_lookup.values()),
    }


@app.get("/fighter-profile")
def fighter_profile(fighter: str) -> dict[str, Any]:
    return build_fighter_profile(fighter)


@app.get("/model-vs-market-evaluation")
def model_vs_market_evaluation() -> dict[str, Any]:
    return build_model_market_evaluation()


@app.get("/model-snapshot-evaluation")
def model_snapshot_evaluation() -> dict[str, Any]:
    return build_model_snapshot_evaluation()


@app.get("/clv-evaluation")
def clv_evaluation() -> dict[str, Any]:
    return build_clv_evaluation()


@app.get("/data-quality")
def data_quality() -> dict[str, Any]:
    return build_data_quality_summary()
