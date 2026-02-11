"""
FastAPI application for the Sims 1 Compatibility Checker.

Endpoints:
  GET /api/sims                       - all sims with person data
  GET /api/sims/{sim_id}/compatibility - ranked compatibility list
  GET /api/families                    - all families
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import Response

from .compatibility import rank_compatibility
from .iff_parser import CharacterInfo, Family, Sim, parse_neighborhood

# ---------------------------------------------------------------------------
# Resolve the UserData path
# ---------------------------------------------------------------------------

# Project root is the parent of the api/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_userdata_path() -> Path:
    """
    Determine the UserData path from the --userdata CLI argument if present,
    otherwise default to UserData/ relative to the project root.
    """
    # FastAPI dev / uvicorn may pass extra args; parse only known ones.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--userdata", type=str, default=None)
    args, _unknown = parser.parse_known_args()

    if args.userdata:
        p = Path(args.userdata)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    return PROJECT_ROOT / "UserData"


# ---------------------------------------------------------------------------
# Shared state (populated at startup)
# ---------------------------------------------------------------------------

_sims: list[Sim] = []
_families: list[Family] = []
_sims_by_id: dict[int, Sim] = {}
_family_by_number: dict[int, Family] = {}
_portraits: dict[int, bytes] = {}  # guid -> BMP bytes


def _load_data() -> None:
    global _sims, _families, _sims_by_id, _family_by_number, _portraits

    userdata = _resolve_userdata_path()
    sims, families, guid_to_info = parse_neighborhood(str(userdata))

    # Build portrait lookup: sim neighbour_id -> BMP bytes
    _portraits = {}
    for s in sims:
        info = guid_to_info.get(s.guid)
        if info and info.portrait:
            _portraits[s.id] = info.portrait

    # Filter out the "Default" family (chunk_id 0) — contains NPCs like
    # maid, thief, repairman, npc_* that aren't meaningful conversation partners.
    _families = [f for f in families if f.chunk_id != 0]
    _sims = [s for s in sims if s.family_number != 0]
    _sims_by_id = {s.id: s for s in _sims}
    _family_by_number = {f.chunk_id: f for f in _families}


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_data()
    yield


# ---------------------------------------------------------------------------
# App & middleware
# ---------------------------------------------------------------------------

app = FastAPI(title="Sims 1 Compatibility Checker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _format_guid(guid: int) -> str:
    return f"0x{guid:08X}"


def _sim_to_dict(sim: Sim) -> dict:
    family = _family_by_number.get(sim.family_number)
    return {
        "id": sim.id,
        "guid": _format_guid(sim.guid),
        "name": sim.name,
        "family_name": family.name if family else "",
        "family_id": sim.family_number,
        "house_number": family.house_number if family else 0,
        "age": sim.age,
        "gender": sim.gender,
        "personality": {
            "nice": sim.personality.nice,
            "active": sim.personality.active,
            "playful": sim.personality.playful,
            "outgoing": sim.personality.outgoing,
            "neat": sim.personality.neat,
        },
        "interests": {
            "travel": sim.interests.travel,
            "violence": sim.interests.violence,
            "politics": sim.interests.politics,
            "sixties": sim.interests.sixties,
            "weather": sim.interests.weather,
            "sports": sim.interests.sports,
            "music": sim.interests.music,
            "outdoors": sim.interests.outdoors,
        },
    }


def _family_to_dict(family: Family) -> dict:
    return {
        "id": family.chunk_id,
        "name": family.name,
        "house_number": family.house_number,
        "budget": family.budget,
        "member_guids": [_format_guid(g) for g in family.member_guids],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/sims")
async def get_sims():
    """Return all sims that have PersonData."""
    return {"sims": [_sim_to_dict(s) for s in _sims]}


@app.get("/api/sims/{sim_id}/compatibility")
async def get_compatibility(sim_id: int):
    """Return ranked compatibility list for a given sim."""
    sim = _sims_by_id.get(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail=f"Sim with id {sim_id} not found")

    rankings = rank_compatibility(sim, _sims)

    return {
        "sim_id": sim_id,
        "rankings": [
            {
                "sim": _sim_to_dict(r.sim),
                "score": r.score,
                "common_interests": r.common_interests,
                "risky_topics": r.risky_topics,
                "personality_match": r.personality_match,
                "relationship_daily": r.relationship_daily,
                "relationship_lifetime": r.relationship_lifetime,
                "is_friend": r.is_friend,
            }
            for r in rankings
        ],
    }


@app.get("/api/sims/{sim_id}/portrait")
async def get_portrait(sim_id: int):
    """Return the sim's portrait as a BMP image."""
    bmp = _portraits.get(sim_id)
    if bmp is None:
        raise HTTPException(status_code=404, detail="No portrait available")
    return Response(content=bmp, media_type="image/bmp")


@app.get("/api/families")
async def get_families():
    """Return all families."""
    return {"families": [_family_to_dict(f) for f in _families]}
