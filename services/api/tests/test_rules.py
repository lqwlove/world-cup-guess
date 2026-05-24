from app.deliberation.rules import count_votes, median_confidence, validate_message


def test_statement_requires_evidence():
    result = validate_message(
        {"msg_type": "STATEMENT", "content": "Argentina EV-home-form-001 strong", "evidence_ids": []},
        phase="Opening",
        valid_evidence_ids={"EV-home-form-001"},
    )
    assert not result.ok


def test_statement_with_valid_evidence():
    result = validate_message(
        {
            "msg_type": "STATEMENT",
            "content": "Form per EV-home-form-001",
            "evidence_ids": ["EV-home-form-001"],
        },
        phase="Opening",
        valid_evidence_ids={"EV-home-form-001"},
    )
    assert result.ok


def test_challenge_requires_refs():
    result = validate_message(
        {"msg_type": "CHALLENGE", "content": "@data wrong", "refs": []},
        phase="CrossExam",
        valid_evidence_ids=set(),
    )
    assert not result.ok


def test_vote_only_in_final():
    result = validate_message(
        {"msg_type": "VOTE", "content": "{}", "refs": []},
        phase="Opening",
        valid_evidence_ids=set(),
        vote_open=False,
    )
    assert not result.ok


def test_count_votes_strong():
    votes = [{"pick": "home"}] * 5 + [{"pick": "away"}] * 2
    r = count_votes(votes)
    assert r["strength"] == "strong"
    assert r["pick"] == "home"


def test_median_confidence():
    votes = [{"p_low": 0.5, "p_high": 0.6}, {"p_low": 0.55, "p_high": 0.65}]
    mid, band = median_confidence(votes)
    assert 0.5 <= mid <= 0.65
    assert band[0] <= band[1]
