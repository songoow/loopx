"""Shared synthetic evidence for real CLI regression, never provider-quality evidence."""

import json


def bind_atomic_evidence(root, config_path, capture_path, basis_path):
    config = json.loads(config_path.read_text())
    config["ranking_policy"] = "evidence_atomic"
    config_path.write_text(json.dumps(config))
    basis = json.loads(basis_path.read_text())
    (root / "observations.txt").write_text(
        "Independent synthetic evidence: the fixture or Unicode probe adds coverage; the other repeats old work."
    )
    basis["evidence"] = [{"ref": "observations.txt"}]
    basis["ranking_evidence"] = [
        {
            "snapshot_id": identity,
            "candidates": {x: ["observations.txt"] for x in snap["baseline_order"]},
        }
        for identity, snap in json.loads(capture_path.read_text())["snapshots"].items()
    ]
    basis_path.write_text(json.dumps(basis))


def atomic_response(request, config, key):
    from loopx_jev.demo import fixture_response

    pair_request = {
        **request,
        "questions": {
            k: v for k, v in request["questions"].items() if k.startswith("pair_")
        },
    }
    envelope = fixture_response(pair_request, config, key)
    for name, question in request["questions"].items():
        if name.startswith("pair_"):
            continue
        choice = "sufficient" if name.startswith("evidence_") else "yes"
        envelope["response"]["answers"][name] = {
            "type": "choice",
            "choice": choice,
            "probabilities": {
                label: float(label == choice) for label in question["criteria"]
            },
        }
    return envelope
