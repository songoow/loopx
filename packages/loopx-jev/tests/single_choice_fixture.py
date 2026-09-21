"""Injected oracle for the single_choice policy; never evidence of measured model quality."""

import json


def bind_single_choice(config_path):
    config = json.loads(config_path.read_text())
    config["ranking_policy"] = "single_choice"
    config_path.write_text(json.dumps(config))


def single_choice_response(request, config, key):
    cards = request["state"]["cards"]
    favored = next(c["id"] for c in cards if "fixture" in c["id"] or "unicode" in c["id"])
    answers = {}
    for name, question in request["questions"].items():
        labels = list(question["criteria"])
        choice = favored if favored in labels else "insufficient_evidence"
        answers[name] = {"type": "choice", "choice": choice, "confidence": 1.0,
                         "probabilities": {v: float(v == choice) for v in labels}}
    return {"dispatch": "response_received", "response": {"model": config.model, "answers": answers}}
