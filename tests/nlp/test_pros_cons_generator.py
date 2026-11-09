from src.nlp.pros_cons_generator import _evaluate


def _row(year, roe, fcf, de, roce):
    return {
        "year": f"Mar {year}",
        "sales": 100.0 + year,
        "net_profit": 10.0,
        "operating_profit": 20.0,
        "depreciation": 2.0,
        "eps": 5.0,
        "dividend_payout": 0.0,
        "borrowings": 25.0,
        "equity_capital": 20.0,
        "reserves": 30.0,
        "assets": 100.0 + year,
        "investments": 0.0,
        "roe": roe,
        "roce": roce,
        "de": de,
        "icr": 1.0,
        "fcf": fcf,
        "rev_cagr": 3.0,
        "pat_cagr": 2.0,
        "eps_cagr": 2.0,
        "opm": 12.0,
        "payout": 10.0,
        "dividend_yield": 0.5,
    }


def test_pros_cons_rules_emit_evidence_and_confidence_above_threshold():
    rows = [_row(year, 25.0, -2.0, 2.5, 8.0) for year in range(2020, 2024)]

    signals = _evaluate({"sector": "Industrials"}, rows)

    assert ("pro", 1, "Consistently high return on equity above 20% demonstrates exceptional capital efficiency") in [
        signal[:3] for signal in signals
    ]
    assert any(signal[0] == "con" and signal[1] == 1 and "2.50" in signal[2] for signal in signals)
    assert any(signal[0] == "con" and signal[1] == 2 for signal in signals)
    assert all(60 < signal[3] <= 100 for signal in signals)
