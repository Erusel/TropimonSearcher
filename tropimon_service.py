import os
import sys
import json
import hashlib
from typing import List

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Boolean,
    ForeignKey,
    BigInteger,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ---------- CONFIG ----------

LOG_FOLDER = r"C:\Users\Erusel\Desktop\TropimonLogs\logs"
DATABASE_URL = "sqlite:///./tropimon_stats.db"

# Legendary species
LEGENDARIES = {
    "cobblemon:articuno", "cobblemon:zaptos", "cobblemon:moltres",
    "cobblemon:suicune", "cobblemon:entei", "cobblemon:raikou",
    "cobblemon:regigigas", "cobblemon:rayquaza",
}

# Mythical species
MYTHICALS = {
    "cobblemon:mew", "cobblemon:celebi", "cobblemon:jirachi",
    "cobblemon:manaphy", "cobblemon:shaymin", "cobblemon:arceus",
    "cobblemon:victini", "cobblemon:marshadow",
}

# ---------- DB SETUP ----------

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Player(Base):
    __tablename__ = "players"

    id = Column(String, primary_key=True, index=True)  # UUID only, no username
    last_seen_timestamp = Column(BigInteger, nullable=True)

    captures = relationship("Capture", back_populates="player")


class Species(Base):
    __tablename__ = "species"

    id = Column(String, primary_key=True, index=True)
    is_legendary = Column(Boolean, default=False)
    is_mythical = Column(Boolean, default=False)

    captures = relationship("Capture", back_populates="species")


class Capture(Base):
    __tablename__ = "captures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, ForeignKey("players.id"), index=True)
    species_id = Column(String, ForeignKey("species.id"), index=True)
    timestamp = Column(BigInteger, nullable=False)
    is_shiny = Column(Boolean, default=False)

    player = relationship("Player", back_populates="captures")
    species = relationship("Species", back_populates="captures")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    init_db()
    return SessionLocal()


# ---------- ANONYMIZER ----------

def anonymize_uuid(uuid: str) -> str:
    """Return a stable anonymous label for a UUID."""
    h = hashlib.sha256(uuid.encode()).hexdigest()[:4].upper()
    return f"Player #{h}"


def reset_database(session):
    session.query(Capture).delete()
    session.query(Species).delete()
    session.query(Player).delete()
    session.commit()


# ---------- DATA LOADER (CLI) ----------

def update_database_from_logs(log_folder: str = LOG_FOLDER):
    """
    Parse both:
    - NEW FORMAT:   logs/<UUID>/POKEMON_CATCH.json
    - OLD FORMAT:   pokemon_logs.json
    """
    init_db()
    session = SessionLocal()

    print("Resetting database...")
    reset_database(session)

    player_cache = {}
    species_cache = {}

    # --- 1) Load OLD format ---
    old_file = os.path.join(log_folder, "pokemon_logs.json")
    load_old_json_file(old_file, session, player_cache, species_cache)

    # --- 2) Load NEW folder-based logs ---
    for folder_name in os.listdir(log_folder):
        folder_path = os.path.join(log_folder, folder_name)

        if not os.path.isdir(folder_path):
            continue

        json_file_path = os.path.join(folder_path, "POKEMON_CATCH.json")
        if not os.path.isfile(json_file_path):
            continue

        print(f"Processing {json_file_path}...")

        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception as e:
            print(f"Error reading {json_file_path}: {e}")
            continue

        for entry in logs:
            player_uuid = entry.get("player")
            datas = entry.get("datas", {})
            species_id = datas.get("Species", "")
            ts = entry.get("timestamp", 0)
            is_shiny = bool(datas.get("Shiny", False))

            if not player_uuid or not species_id:
                continue

            if player_uuid not in player_cache:
                player = Player(id=player_uuid, last_seen_timestamp=ts)
                session.add(player)
                player_cache[player_uuid] = player
            else:
                player = player_cache[player_uuid]
                if ts > (player.last_seen_timestamp or 0):
                    player.last_seen_timestamp = ts

            if species_id not in species_cache:
                species = Species(
                    id=species_id,
                    is_legendary=species_id in LEGENDARIES,
                    is_mythical=species_id in MYTHICALS,
                )
                session.add(species)
                species_cache[species_id] = species
            else:
                species = species_cache[species_id]

            capture = Capture(
                player=player,
                species=species,
                timestamp=ts,
                is_shiny=is_shiny,
            )
            session.add(capture)

    session.commit()
    session.close()
    print("Database update complete.")



# ---------- FASTAPI APP SETUP ----------

app = FastAPI(title="Tropimon Stats – Anonymous")

# static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------- API HELPERS ----------

def api_top_captures(session, limit: int = 10):
    q = (
        session.query(
            Capture.player_id,
            func.count(Capture.id).label("count"),
        )
        .group_by(Capture.player_id)
        .order_by(func.count(Capture.id).desc())
        .limit(limit)
    )
    return [{"player": anonymize_uuid(pid), "count": c} for pid, c in q]


def api_top_shiny(session, limit: int = 10):
    q = (
        session.query(
            Capture.player_id,
            func.count(Capture.id),
        )
        .filter(Capture.is_shiny == True)
        .group_by(Capture.player_id)
        .order_by(func.count(Capture.id).desc())
        .limit(limit)
    )
    return [{"player": anonymize_uuid(pid), "count": c} for pid, c in q]


def api_top_legendaries(session, limit: int = 10):
    q = (
        session.query(
            Capture.player_id,
            func.count(Capture.id),
        )
        .join(Species, Capture.species_id == Species.id)
        .filter(Species.is_legendary == True)
        .group_by(Capture.player_id)
        .order_by(func.count(Capture.id).desc())
        .limit(limit)
    )
    return [{"player": anonymize_uuid(pid), "count": c} for pid, c in q]


def api_top_mythicals(session, limit: int = 10):
    q = (
        session.query(
            Capture.player_id,
            func.count(Capture.id),
        )
        .join(Species, Capture.species_id == Species.id)
        .filter(Species.is_mythical == True)
        .group_by(Capture.player_id)
        .order_by(func.count(Capture.id).desc())
        .limit(limit)
    )
    return [{"player": anonymize_uuid(pid), "count": c} for pid, c in q]


def api_top_species(session, limit: int = 50):
    q = (
        session.query(
            Capture.species_id,
            func.count(Capture.id),
        )
        .join(Species, Capture.species_id == Species.id)
        .filter(Species.is_legendary == False, Species.is_mythical == False)
        .group_by(Capture.species_id)
        .order_by(func.count(Capture.id).desc())
        .limit(limit)
    )
    return [{"species": sid, "count": c} for sid, c in q]


def api_top_shiny_species(session, limit: int = 10):
    q = (
        session.query(
            Capture.species_id,
            func.count(Capture.id),
        )
        .filter(Capture.is_shiny == True)
        .group_by(Capture.species_id)
        .order_by(func.count(Capture.id).desc())
        .limit(limit)
    )
    return [{"species": sid, "count": c} for sid, c in q]


def api_summary(session):
    total_captures = session.query(func.count(Capture.id)).scalar() or 0
    total_shiny = session.query(func.count(Capture.id)).filter(Capture.is_shiny == True).scalar() or 0
    total_legendaries = (
        session.query(func.count(Capture.id))
        .join(Species, Capture.species_id == Species.id)
        .filter(Species.is_legendary == True)
        .scalar()
        or 0
    )
    total_mythicals = (
        session.query(func.count(Capture.id))
        .join(Species, Capture.species_id == Species.id)
        .filter(Species.is_mythical == True)
        .scalar()
        or 0
    )

    return {
        "total_captures": total_captures,
        "total_shiny": total_shiny,
        "total_legendaries": total_legendaries,
        "total_mythicals": total_mythicals,
    }


def api_species_detail(session, species_id: str):
    total = (
        session.query(func.count(Capture.id))
        .filter(Capture.species_id == species_id)
        .scalar()
        or 0
    )
    shiny = (
        session.query(func.count(Capture.id))
        .filter(Capture.species_id == species_id, Capture.is_shiny == True)
        .scalar()
        or 0
    )

    q = (
        session.query(
            Capture.player_id,
            func.count(Capture.id),
        )
        .filter(Capture.species_id == species_id)
        .group_by(Capture.player_id)
        .order_by(func.count(Capture.id).desc())
        .limit(10)
    )

    rows = [{"player": anonymize_uuid(pid), "count": c} for pid, c in q]

    return {
        "species": species_id,
        "total": total,
        "shiny": shiny,
        "top_players": rows,
    }


# ---------- API ROUTES (JSON) ----------

@app.get("/api/summary")
def api_get_summary():
    session = get_session()
    data = api_summary(session)
    session.close()
    return data



@app.get("/api/top/captures")
def api_get_top_captures(limit: int = 10):
    session = get_session()
    data = api_top_captures(session, limit=limit)
    session.close()
    return data


@app.get("/api/top/shiny")
def api_get_top_shiny(limit: int = 10):
    session = get_session()
    data = api_top_shiny(session, limit=limit)
    session.close()
    return data


@app.get("/api/top/legendaries")
def api_get_top_legendaries(limit: int = 10):
    session = get_session()
    data = api_top_legendaries(session, limit=limit)
    session.close()
    return data


@app.get("/api/top/mythicals")
def api_get_top_mythicals(limit: int = 10):
    session = get_session()
    data = api_top_mythicals(session, limit=limit)
    session.close()
    return data


@app.get("/api/top/species")
def api_get_top_species(limit: int = 50):
    session = get_session()
    data = api_top_species(session, limit=limit)
    session.close()
    return data


@app.get("/api/top/shiny-species")
def api_get_top_shiny_species(limit: int = 10):
    session = get_session()
    data = api_top_shiny_species(session, limit=limit)
    session.close()
    return data


@app.get("/api/species/{species_id}")
def api_get_species_detail(species_id: str):
    session = get_session()
    data = api_species_detail(session, species_id)
    session.close()
    return data


# ---------- PAGE ROUTES (HTML) ----------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    # Le JS va appeler /api/summary etc. pour remplir les cartes et graphiques.
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/species/{species_id}", response_class=HTMLResponse)
def species_page(request: Request, species_id: str):
    session = get_session()
    data = api_species_detail(session, species_id)
    session.close()

    return templates.TemplateResponse(
        "species.html",
        {
            "request": request,
            "species": data["species"],
            "total": data["total"],
            "shiny": data["shiny"],
            "rows": data["top_players"],
        },
    )


@app.get("/search/species", response_class=HTMLResponse)
def search_species_html(request: Request, species: str = Query(...)):
    session = get_session()
    data = api_species_detail(session, species)
    session.close()

    return templates.TemplateResponse(
        "species.html",
        {
            "request": request,
            "species": data["species"],
            "total": data["total"],
            "shiny": data["shiny"],
            "rows": data["top_players"],
        },
    )

def load_old_json_file(path: str, session, player_cache, species_cache):
    """
    Load old format: pokemon_logs.json
    Structure:
    {
        "playerUUID": [
            {
                "pokemon": {...},
                "captureTimestamp": int,
                "uuid": "playerUUID",
                "playerName": "Chipitos_"
            },
            ...
        ]
    }
    """
    if not os.path.isfile(path):
        print("No old-format pokemon_logs.json found.")
        return

    print(f"Loading old-format file: {path}")

    try:
        with open(path, "r", encoding="utf8") as f:
            data = json.load(f)
    except Exception as e:
        print("Error reading old file:", e)
        return

    for player_uuid, captures in data.items():

        for entry in captures:
            poke = entry.get("pokemon", {})
            species_id = poke.get("Species")
            ts = entry.get("captureTimestamp", 0)
            is_shiny = bool(poke.get("Shiny", False))

            if not species_id or not player_uuid:
                continue

            # PLAYER
            if player_uuid not in player_cache:
                player = Player(id=player_uuid, last_seen_timestamp=ts)
                session.add(player)
                player_cache[player_uuid] = player
            else:
                player = player_cache[player_uuid]
                if ts > (player.last_seen_timestamp or 0):
                    player.last_seen_timestamp = ts

            # SPECIES
            if species_id not in species_cache:
                species = Species(
                    id=species_id,
                    is_legendary=species_id in LEGENDARIES,
                    is_mythical=species_id in MYTHICALS
                )
                session.add(species)
                species_cache[species_id] = species
            else:
                species = species_cache[species_id]

            # CAPTURE
            cap = Capture(
                player=player,
                species=species,
                timestamp=ts,
                is_shiny=is_shiny
            )
            session.add(cap)

    print("Old-format logs imported successfully.")


# ---------- CLI ----------

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "load":
        update_database_from_logs(LOG_FOLDER)
    else:
        print("Usage:")
        print("  python tropimon_service.py load")
        print("Then run:")
        print("  uvicorn tropimon_service:app --host 0.0.0.0 --port 8000")
