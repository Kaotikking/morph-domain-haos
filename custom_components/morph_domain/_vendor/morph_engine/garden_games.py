"""Small, replay-safe Gardens games. No custody or breeding effects."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any

GAMES = {"MATCHING", "WHICH_HAND", "FOLLOW_PATTERN"}
MAX_TURNS = 64


class GardenGameError(ValueError):
    pass


def _draw(seed: str, count: int) -> list[int]:
    values = list(range(count))
    values.sort(key=lambda item: sha256(f"{seed}:{item}".encode()).digest())
    return values


def start_game(*, game_id: str, morph_id: str, operator_id: str, game: str,
               started_at: str) -> dict[str, Any]:
    if not all(isinstance(value, str) and value for value in
               (game_id, morph_id, operator_id, started_at)) or game not in GAMES:
        raise GardenGameError("invalid game identity")
    seed = f"{game_id}:{morph_id}:{operator_id}"
    if game == "MATCHING":
        order = _draw(seed, 16)
        secret = [0] * 16
        for card, position in enumerate(order):
            secret[position] = card // 2
    elif game == "WHICH_HAND":
        secret = [_draw(f"{seed}:{round_id}", 2)[0] for round_id in range(5)]
    else:
        secret = [_draw(f"{seed}:{round_id}", 4)[:round_id + 2]
                  for round_id in range(3)]
    return {"game_id": game_id, "morph_id": morph_id, "operator_id": operator_id,
            "game": game, "started_at": started_at, "secret": secret,
            "turn": 0, "score": 0, "matched": [], "move_ids": [], "responses": {},
            "choices": {},
            "finished": False, "rewarded": False}


def public_state(session: dict[str, Any]) -> dict[str, Any]:
    result = {key: session[key] for key in
              ("game_id", "morph_id", "game", "turn", "score", "finished", "rewarded")}
    if session["game"] == "MATCHING":
        result["board"] = [value if index in session["matched"] else None
                           for index, value in enumerate(session["secret"])]
    elif session["game"] == "WHICH_HAND":
        result["round"] = min(session["turn"] + 1, 5)
    elif not session["finished"]:
        result["pattern"] = session["secret"][session["turn"]]
    return result


def move(session: dict[str, Any], *, move_id: str, choice: Any) -> dict[str, Any]:
    if not isinstance(move_id, str) or not move_id:
        raise GardenGameError("move id required")
    if move_id in session["move_ids"]:
        if session["choices"][move_id] != choice:
            raise GardenGameError("move id payload changed")
        return dict(session["responses"][move_id])
    if session["finished"] or session["turn"] >= MAX_TURNS:
        raise GardenGameError("game is finished")
    game = session["game"]
    if game == "MATCHING":
        if (not isinstance(choice, list) or len(choice) != 2
                or any(type(index) is not int or not 0 <= index < 16 for index in choice)
                or choice[0] == choice[1]
                or any(index in session["matched"] for index in choice)):
            raise GardenGameError("choose two unmatched tiles")
        correct = session["secret"][choice[0]] == session["secret"][choice[1]]
        if correct:
            session["matched"].extend(choice)
            session["score"] += 1
        session["finished"] = len(session["matched"]) == 16
    elif game == "WHICH_HAND":
        if type(choice) is not int or choice not in (0, 1):
            raise GardenGameError("choose left or right")
        correct = choice == session["secret"][session["turn"]]
        session["score"] += int(correct)
        session["finished"] = session["turn"] == 4
    else:
        expected = session["secret"][session["turn"]]
        if (not isinstance(choice, list) or len(choice) != len(expected)
                or any(type(value) is not int or not 0 <= value < 4 for value in choice)):
            raise GardenGameError("repeat the shown pattern")
        correct = choice == expected
        session["score"] += int(correct)
        session["finished"] = session["turn"] == 2
    session["turn"] += 1
    session["move_ids"].append(move_id)
    session["choices"][move_id] = deepcopy(choice)
    result = public_state(session)
    result["correct"] = correct
    if game == "MATCHING":
        result["revealed"] = [[index, session["secret"][index]] for index in choice]
    elif game == "WHICH_HAND":
        result["revealed_hand"] = session["secret"][session["turn"] - 1]
    session["responses"][move_id] = dict(result)
    return result
