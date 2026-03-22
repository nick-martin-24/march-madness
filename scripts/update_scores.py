"""
update_scores.py
Fetches 2026 NCAA Men's Tournament scores from ESPN (groups=50) and updates the Gist.
Filters to tournament games by checking if both teams are known tournament teams.
"""

import json
import os
import requests
from datetime import datetime, timedelta, timezone

GIST_ID    = os.environ["GIST_ID"]
GIST_TOKEN = os.environ["GIST_TOKEN"]
GIST_FILE  = "pool2026.json"
ESPN_BASE  = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"

ROUND_NAMES = {
    0: "First Four",  1: "First Round", 2: "Second Round",
    3: "Sweet 16",    4: "Elite Eight", 5: "Final Four",  6: "Championship"
}
NOTE_TO_ROUND = {
    "First Four": 0, "First Round": 1, "Second Round": 2,
    "Sweet 16": 3, "Elite Eight": 4, "Final Four": 5, "Championship": 6
}
ROUND_BY_DATE = {
    "2026-03-17": 0, "2026-03-18": 0,
    "2026-03-19": 1, "2026-03-20": 1,
    "2026-03-21": 2, "2026-03-22": 2,
    "2026-03-26": 3, "2026-03-27": 3,
    "2026-03-28": 4, "2026-03-29": 4,
    "2026-04-04": 5,
    "2026-04-06": 6,
}

# Hardcoded seeds — source of truth
SEED_MAP = {
    "Duke": 1, "Arizona": 1, "Michigan": 1, "Florida": 1,
    "UConn": 2, "Purdue": 2, "Iowa State": 2, "Houston": 2,
    "Michigan State": 3, "Gonzaga": 3, "Virginia": 3, "Illinois": 3,
    "Kansas": 4, "Arkansas": 4, "Alabama": 4, "Nebraska": 4,
    "St. John's": 5, "Wisconsin": 5, "Texas Tech": 5, "Vanderbilt": 5,
    "Louisville": 6, "BYU": 6, "Tennessee": 6, "North Carolina": 6,
    "UCLA": 7, "Miami (FL)": 7, "Kentucky": 7, "Saint Mary's": 7,
    "Ohio State": 8, "Villanova": 8, "Georgia": 8, "Clemson": 8,
    "TCU": 9, "Utah State": 9, "Saint Louis": 9, "Iowa": 9,
    "UCF": 10, "Missouri": 10, "Santa Clara": 10, "Texas A&M": 10,
    "South Florida": 11, "Texas": 11, "SMU": 11, "VCU": 11,
    "NC State": 11, "Miami (OH)": 11,
    "Northern Iowa": 12, "High Point": 12, "Akron": 12, "McNeese": 12,
    "Cal Baptist": 13, "Hawaii": 13, "Hofstra": 13, "Troy": 13,
    "North Dakota State": 14, "Kennesaw State": 14, "Wright State": 14, "Penn": 14,
    "Furman": 15, "Queens (NC)": 15, "Tennessee State": 15, "Idaho": 15,
    "Siena": 16, "LIU": 16, "Howard": 16, "UMBC": 16,
    "Prairie View A&M": 16, "Lehigh": 16,
}

NAME_MAP = {
    "Duke Blue Devils": "Duke", "Arizona Wildcats": "Arizona",
    "Michigan Wolverines": "Michigan", "Florida Gators": "Florida",
    "UConn Huskies": "UConn", "Purdue Boilermakers": "Purdue",
    "Iowa State Cyclones": "Iowa State", "Houston Cougars": "Houston",
    "Michigan State Spartans": "Michigan State", "Gonzaga Bulldogs": "Gonzaga",
    "Virginia Cavaliers": "Virginia", "Illinois Fighting Illini": "Illinois",
    "Kansas Jayhawks": "Kansas", "Arkansas Razorbacks": "Arkansas",
    "Alabama Crimson Tide": "Alabama", "Nebraska Cornhuskers": "Nebraska",
    "St. John's Red Storm": "St. John's", "Wisconsin Badgers": "Wisconsin",
    "Texas Tech Red Raiders": "Texas Tech", "Vanderbilt Commodores": "Vanderbilt",
    "Louisville Cardinals": "Louisville", "BYU Cougars": "BYU",
    "Tennessee Volunteers": "Tennessee", "North Carolina Tar Heels": "North Carolina",
    "UCLA Bruins": "UCLA", "Miami Hurricanes": "Miami (FL)",
    "Miami (FL) Hurricanes": "Miami (FL)", "Kentucky Wildcats": "Kentucky",
    "Saint Mary's Gaels": "Saint Mary's", "Ohio State Buckeyes": "Ohio State",
    "Villanova Wildcats": "Villanova", "Georgia Bulldogs": "Georgia",
    "Clemson Tigers": "Clemson", "TCU Horned Frogs": "TCU",
    "Utah State Aggies": "Utah State", "Saint Louis Billikens": "Saint Louis",
    "Iowa Hawkeyes": "Iowa", "UCF Knights": "UCF", "Missouri Tigers": "Missouri",
    "Santa Clara Broncos": "Santa Clara", "Texas A&M Aggies": "Texas A&M",
    "South Florida Bulls": "South Florida", "Texas Longhorns": "Texas",
    "SMU Mustangs": "SMU", "VCU Rams": "VCU",
    "Northern Iowa Panthers": "Northern Iowa", "High Point Panthers": "High Point",
    "Akron Zips": "Akron", "McNeese Cowboys": "McNeese",
    "California Baptist Lancers": "Cal Baptist", "Cal Baptist Lancers": "Cal Baptist",
    "Hawaii Rainbow Warriors": "Hawaii", "Hawai'i Rainbow Warriors": "Hawaii",
    "Hofstra Pride": "Hofstra", "Troy Trojans": "Troy",
    "North Dakota State Bison": "North Dakota State",
    "Kennesaw State Owls": "Kennesaw State", "Wright State Raiders": "Wright State",
    "Penn Quakers": "Penn", "Furman Paladins": "Furman",
    "Queens Royals": "Queens (NC)", "Queens University Royals": "Queens (NC)",
    "Tennessee State Tigers": "Tennessee State", "Idaho Vandals": "Idaho",
    "NC State Wolfpack": "NC State", "Miami (OH) RedHawks": "Miami (OH)",
    "Howard Bison": "Howard", "UMBC Retrievers": "UMBC",
    "LIU Sharks": "LIU", "Siena Saints": "Siena",
    "Prairie View A&M Panthers": "Prairie View A&M",
    "Lehigh Mountain Hawks": "Lehigh",
}

POOL_TEAMS = set(SEED_MAP.keys())


def normalize(name):
    return NAME_MAP.get(name, name)


def fetch_espn(date_str):
    """Fetch all college basketball games for a date using groups=50."""
    try:
        r = requests.get(
            f"{ESPN_BASE}/scoreboard",
            params={"groups": "50", "limit": "200", "dates": date_str},
            timeout=10
        )
        r.raise_for_status()
        return r.json().get("events", [])
    except Exception as e:
        print(f"  ESPN fetch failed ({date_str}): {e}")
        return []


def parse_event(ev):
    try:
        comp = ev["competitions"][0]

        # Get round from note headline
        note = ""
        for n in ev.get("notes", []):
            note = n.get("headline", "")
            if note:
                break

        note_round = -1
        for key, val in NOTE_TO_ROUND.items():
            if key in note:
                note_round = val
                break

        # Date is authoritative — ESPN notes are sometimes wrong
        date_str = ev.get("date", "")[:10]
        date_round = ROUND_BY_DATE.get(date_str, -1)

        # Use date-based round if available, fall back to note
        if date_round >= 0:
            round_num = date_round
        elif note_round >= 0:
            round_num = note_round
        else:
            return None

        # Parse teams
        teams = []
        for c in comp.get("competitors", []):
            raw  = c.get("team", {}).get("displayName") or c.get("team", {}).get("name", "")
            name = normalize(raw)
            seed = SEED_MAP.get(name, 0)
            score = int(c.get("score") or 0)
            won   = bool(c.get("winner", False))
            teams.append({"name": name, "seed": seed, "score": score, "winner": won})

        if len(teams) < 2:
            return None

        # Filter: at least one team must be a known tournament team
        if not any(t["name"] in POOL_TEAMS for t in teams):
            return None

        status_type = comp.get("status", {}).get("type", {})
        state  = status_type.get("state", "pre")
        clock  = comp.get("status", {}).get("displayClock", "")
        period = comp.get("status", {}).get("period", 0)
        detail = status_type.get("shortDetail", "")

        return {
            "id":           ev["id"],
            "round":        round_num,
            "roundName":    ROUND_NAMES[round_num],
            "status":       state,
            "statusDetail": "Final" if state == "post" else detail,
            "displayClock": clock,
            "period":       period,
            "teams":        teams,
        }
    except Exception as e:
        print(f"  parse_event error: {e}")
        return None


def fetch_all_games():
    now   = datetime.now(timezone.utc)
    games = {}

    for offset in range(-4, 2):
        d = (now + timedelta(days=offset)).strftime("%Y%m%d")
        print(f"  Fetching {d}...")
        events = fetch_espn(d)
        count = 0
        for ev in events:
            g = parse_event(ev)
            if g and g["id"] not in games:
                games[g["id"]] = g
                count += 1
                print(f"    + {g['roundName']}: {g['teams'][0]['name']} vs {g['teams'][1]['name']} [{g['status']}]")
        if count == 0:
            print(f"    (no tournament games on this date)")

    print(f"  Total: {len(games)} tournament games")
    return list(games.values())


def load_gist():
    r = requests.get(
        f"https://api.github.com/gists/{GIST_ID}",
        headers={"Authorization": f"token {GIST_TOKEN}"},
        timeout=10
    )
    r.raise_for_status()
    return json.loads(r.json()["files"][GIST_FILE]["content"])


def save_gist(data):
    r = requests.patch(
        f"https://api.github.com/gists/{GIST_ID}",
        headers={"Authorization": f"token {GIST_TOKEN}", "Content-Type": "application/json"},
        json={"files": {GIST_FILE: {"content": json.dumps(data, indent=2)}}},
        timeout=10
    )
    r.raise_for_status()
    print("  Gist updated successfully.")


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
        print("No tournament games found — skipping update.")
        return

    pool_data["games"]          = games
    pool_data["gamesUpdatedAt"] = datetime.now(timezone.utc).isoformat()

    print("Saving to Gist...")
    try:
        save_gist(pool_data)
    except Exception as e:
        print(f"Failed to save Gist: {e}")
        return

    finals = [g for g in games if g["status"] == "post"]
    live   = [g for g in games if g["status"] == "in"]
    sched  = [g for g in games if g["status"] == "pre"]
    print(f"  Final: {len(finals)}  Live: {len(live)}  Scheduled: {len(sched)}")
    print("Done.")


if __name__ == "__main__":
    main()
