"""
update_scores.py
Fetches 2026 NCAA tournament scores from ESPN and updates the Gist.
Runs via GitHub Actions every 5 minutes during tournament hours.
"""

import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ── Config ────────────────────────────────────────────────────────────────────
GIST_ID    = os.environ["GIST_ID"]
GIST_TOKEN = os.environ["GIST_TOKEN"]
GIST_FILE  = "pool2026.json"

ESPN_BASE  = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"

# ── Round detection by date ───────────────────────────────────────────────────
ROUND_BY_DATE = {
    "2026-03-17": 0, "2026-03-18": 0,   # First Four
    "2026-03-19": 1, "2026-03-20": 1,   # First Round
    "2026-03-21": 2, "2026-03-22": 2,   # Second Round
    "2026-03-26": 3, "2026-03-27": 3,   # Sweet 16
    "2026-03-28": 4, "2026-03-29": 4,   # Elite Eight
    "2026-04-04": 5,                     # Final Four
    "2026-04-06": 6,                     # Championship
}
ROUND_NAMES = {
    0: "First Four", 1: "First Round", 2: "Second Round",
    3: "Sweet 16",   4: "Elite Eight", 5: "Final Four", 6: "Championship"
}
NOTE_TO_ROUND = {
    "First Four": 0, "First Round": 1, "Second Round": 2,
    "Sweet 16": 3, "Elite Eight": 4, "Final Four": 5, "Championship": 6
}

# ── ESPN full names → pool short names ───────────────────────────────────────
NAME_MAP = {
    "Duke Blue Devils": "Duke",
    "Arizona Wildcats": "Arizona",
    "Michigan Wolverines": "Michigan",
    "Florida Gators": "Florida",
    "UConn Huskies": "UConn",
    "Purdue Boilermakers": "Purdue",
    "Iowa State Cyclones": "Iowa State",
    "Houston Cougars": "Houston",
    "Michigan State Spartans": "Michigan State",
    "Gonzaga Bulldogs": "Gonzaga",
    "Virginia Cavaliers": "Virginia",
    "Illinois Fighting Illini": "Illinois",
    "Kansas Jayhawks": "Kansas",
    "Arkansas Razorbacks": "Arkansas",
    "Alabama Crimson Tide": "Alabama",
    "Nebraska Cornhuskers": "Nebraska",
    "St. John's Red Storm": "St. John's",
    "Wisconsin Badgers": "Wisconsin",
    "Texas Tech Red Raiders": "Texas Tech",
    "Vanderbilt Commodores": "Vanderbilt",
    "Louisville Cardinals": "Louisville",
    "BYU Cougars": "BYU",
    "Tennessee Volunteers": "Tennessee",
    "North Carolina Tar Heels": "North Carolina",
    "UCLA Bruins": "UCLA",
    "Miami Hurricanes": "Miami (FL)",
    "Kentucky Wildcats": "Kentucky",
    "Saint Mary's Gaels": "Saint Mary's",
    "Ohio State Buckeyes": "Ohio State",
    "Villanova Wildcats": "Villanova",
    "Georgia Bulldogs": "Georgia",
    "Clemson Tigers": "Clemson",
    "TCU Horned Frogs": "TCU",
    "Utah State Aggies": "Utah State",
    "Saint Louis Billikens": "Saint Louis",
    "Iowa Hawkeyes": "Iowa",
    "UCF Knights": "UCF",
    "Missouri Tigers": "Missouri",
    "Santa Clara Broncos": "Santa Clara",
    "Texas A&M Aggies": "Texas A&M",
    "South Florida Bulls": "South Florida",
    "Texas Longhorns": "Texas",
    "SMU Mustangs": "SMU",
    "VCU Rams": "VCU",
    "Northern Iowa Panthers": "Northern Iowa",
    "High Point Panthers": "High Point",
    "Akron Zips": "Akron",
    "McNeese Cowboys": "McNeese",
    "California Baptist Lancers": "Cal Baptist",
    "Cal Baptist Lancers": "Cal Baptist",
    "Hawaii Rainbow Warriors": "Hawaii",
    "Hawai'i Rainbow Warriors": "Hawaii",
    "Hofstra Pride": "Hofstra",
    "Troy Trojans": "Troy",
    "North Dakota State Bison": "North Dakota State",
    "Kennesaw State Owls": "Kennesaw State",
    "Wright State Raiders": "Wright State",
    "Penn Quakers": "Penn",
    "Furman Paladins": "Furman",
    "Queens Royals": "Queens (NC)",
    "Tennessee State Tigers": "Tennessee State",
    "Idaho Vandals": "Idaho",
    "NC State Wolfpack": "NC State",
    "Miami (OH) RedHawks": "Miami (OH)",
    "Howard Bison": "Howard",
    "UMBC Retrievers": "UMBC",
    "LIU Sharks": "LIU",
    "Siena Saints": "Siena",
    "Prairie View A&M Panthers": "Prairie View A&M",
    "Lehigh Mountain Hawks": "Lehigh",
}

# ── Fetch ESPN scoreboard for a date string (YYYYMMDD) ───────────────────────
def fetch_espn_date(date_str):
    url = f"{ESPN_BASE}/scoreboard"
    params = {"groups": "50", "limit": "100", "dates": date_str}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("events", [])
    except Exception as e:
        print(f"  ESPN fetch failed for {date_str}: {e}")
        return []

# ── Parse a single ESPN event into our game format ───────────────────────────
def parse_event(ev):
    try:
        comp = ev["competitions"][0]
        note = ev.get("notes", [{}])[0].get("headline", "")
        date_str = ev.get("date", "")[:10]

        # Determine round
        round_num = -1
        for key, val in NOTE_TO_ROUND.items():
            if key in note:
                round_num = val
                break
        if round_num < 0:
            round_num = ROUND_BY_DATE.get(date_str, -1)
        if round_num < 0:
            # season type 3 = postseason, catch anything we missed
            if ev.get("season", {}).get("type") != 3:
                return None
            round_num = ROUND_BY_DATE.get(date_str, -1)
        if round_num < 0:
            return None

        status_obj = comp.get("status", {})
        state      = status_obj.get("type", {}).get("state", "pre")   # pre/in/post
        clock      = status_obj.get("displayClock", "")
        period     = status_obj.get("period", 0)
        detail     = status_obj.get("type", {}).get("shortDetail", "")

        teams = []
        for c in comp.get("competitors", []):
            raw_name  = c.get("team", {}).get("displayName") or c.get("team", {}).get("name", "")
            team_name = NAME_MAP.get(raw_name, raw_name)  # normalize to pool name
            seed = int(c.get("curatedRank", {}).get("current") or c.get("seed") or 0)
            score = int(c.get("score") or 0)
            winner = bool(c.get("winner", False))
            teams.append({
                "name":    team_name,
                "seed":    seed,
                "score":   score,
                "winner":  winner
            })

        if len(teams) < 2:
            return None

        return {
            "id":           ev["id"],
            "round":        round_num,
            "roundName":    ROUND_NAMES.get(round_num, note),
            "status":       state,
            "statusDetail": "Final" if state == "post" else detail,
            "displayClock": clock,
            "period":       period,
            "teams":        teams
        }
    except Exception as e:
        print(f"  parse_event error: {e}")
        return None

# ── Fetch all relevant tournament dates ──────────────────────────────────────
def fetch_all_games():
    now = datetime.now(timezone.utc)
    games   = {}   # id -> game (dedup)

    # Fetch a 5-day window: 3 days back through tomorrow
    for offset in range(-3, 2):
        d = (now + timedelta(days=offset)).strftime("%Y%m%d")
        print(f"  Fetching ESPN for {d}...")
        for ev in fetch_espn_date(d):
            g = parse_event(ev)
            if g and g["id"] not in games:
                games[g["id"]] = g

    print(f"  Total tournament games found: {len(games)}")
    return list(games.values())

# ── Load current Gist content ─────────────────────────────────────────────────
def load_gist():
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GIST_TOKEN}"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    raw = r.json()["files"][GIST_FILE]["content"]
    return json.loads(raw)

# ── Save updated content back to Gist ────────────────────────────────────────
def save_gist(data):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Content-Type":  "application/json"
    }
    payload = {
        "files": {
            GIST_FILE: {
                "content": json.dumps(data, indent=2)
            }
        }
    }
    r = requests.patch(url, headers=headers, json=payload, timeout=10)
    r.raise_for_status()
    print("  Gist updated successfully.")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=== NCAA Score Updater ===")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    print("Loading Gist...")
    try:
        pool_data = load_gist()
    except Exception as e:
        print(f"Failed to load Gist: {e}")
        return

    print("Fetching scores from ESPN...")
    games = fetch_all_games()

    if not games:
        print("No tournament games found — skipping Gist update.")
        return

    pool_data["games"]          = games
    pool_data["gamesUpdatedAt"] = datetime.now(timezone.utc).isoformat()

    print("Saving to Gist...")
    try:
        save_gist(pool_data)
    except Exception as e:
        print(f"Failed to save Gist: {e}")
        return

    # Print summary
    finals  = [g for g in games if g["status"] == "post"]
    live    = [g for g in games if g["status"] == "in"]
    sched   = [g for g in games if g["status"] == "pre"]
    print(f"  Final: {len(finals)}  Live: {len(live)}  Scheduled: {len(sched)}")
    print("Done.")

if __name__ == "__main__":
    main()
