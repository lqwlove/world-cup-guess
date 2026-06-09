from app.services.market_service import _parse_gamma_response


MEX_RSA_EVENT = [
    {
        "title": "Mexico vs. South Africa",
        "slug": "fifwc-mex-rsa-2026-06-11",
        "volume": 442505.23,
        "markets": [
            {
                "slug": "fifwc-mex-rsa-2026-06-11-mex",
                "groupItemTitle": "Mexico",
                "question": "Will Mexico win on 2026-06-11?",
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.685", "0.315"]',
            },
            {
                "slug": "fifwc-mex-rsa-2026-06-11-draw",
                "groupItemTitle": "Draw (Mexico vs. South Africa)",
                "question": "Will Mexico vs. South Africa end in a draw?",
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.205", "0.795"]',
            },
            {
                "slug": "fifwc-mex-rsa-2026-06-11-rsa",
                "groupItemTitle": "South Africa",
                "question": "Will South Africa win on 2026-06-11?",
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.105", "0.895"]',
            },
        ],
    }
]

OUTCOME_MAP = {
    "home": "mexico",
    "draw": "draw",
    "away": "south africa",
}


def test_parse_split_yes_no_markets():
    probs, meta = _parse_gamma_response(MEX_RSA_EVENT, OUTCOME_MAP)
    assert abs(probs["home"] - 0.685) < 0.01
    assert abs(probs["draw"] - 0.205) < 0.01
    assert abs(probs["away"] - 0.105) < 0.01
    assert meta["title"] == "Mexico vs. South Africa"
    assert len(meta["markets"]) == 3


def test_parse_legacy_single_market():
    legacy = [
        {
            "title": "Demo",
            "markets": [
                {
                    "outcomes": ["home", "draw", "away"],
                    "outcomePrices": ["0.5", "0.3", "0.2"],
                }
            ],
        }
    ]
    probs, _ = _parse_gamma_response(
        legacy, {"home": "home", "draw": "draw", "away": "away"}
    )
    assert probs["home"] == 0.5
    assert probs["draw"] == 0.3
    assert probs["away"] == 0.2
