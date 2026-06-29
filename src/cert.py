from datetime import datetime


def boost_score(score: float) -> float:
    """Provenance certificate score boost: 1 - (1 - score)^3.25"""
    return 1 - (1 - score) ** 3.25


def check_provenance_certificate(metadata: dict) -> bool:
    """
    Returns True if the metadata meets provenance certificate requirements:
    - Platform must be desktop_app
    - Zero pastes from elsewhere
    - At least 3 sessions of >= 1 hour each
    """
    if not metadata:
        return False
    if metadata.get("platform") != "desktop_app":
        return False
    if metadata.get("pastes_from_elsewhere", 1) != 0:
        return False
    sessions = metadata.get("sessions", [])
    qualifying = 0
    for s in sessions:
        try:
            start = datetime.fromisoformat(s["start"])
            end = datetime.fromisoformat(s["end"])
            if (end - start).total_seconds() >= 3600:
                qualifying += 1
        except (KeyError, ValueError):
            continue
    return qualifying >= 3
