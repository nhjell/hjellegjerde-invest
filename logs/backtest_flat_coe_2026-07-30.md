# Flat-CoE residual income backtest — 2026-07-30

**Question tested:** if every bank is valued with an identical 10% cost of
equity (risk differences deliberately neutralised), does ranking banks by
residual-income mispricing — using the same trajectory-aware forecast engine
as the live model, restricted to point-in-time information — predict
subsequent quarterly returns within Australia and within Thailand?

**Method:** see the module docstring of `src/backtest_flat_coe.py` for the
full contract. Quarterly rebalance; 90-day publication lag on annual
reports; equal-weighted legs; each region runs in its own currency.
Portfolios: top-third long (headline), cheap-half vs expensive-half spread
(diagnostic), equal-weight regional benchmark.

## AUS (15 quarterly periods, 2022-09-30 → 2026-06-30)

| Leg | CAGR | Vol (ann.) | Sharpe | Max DD | Hit rate |
|---|---|---|---|---|---|
| top_third | 21.1% | 14.2% | 1.45 | -8.0% | 80% |
| cheap_half | 20.5% | 13.9% | 1.43 | -8.0% | 67% |
| exp_half | 9.3% | 16.3% | 0.63 | -19.2% | 53% |
| benchmark | 14.8% | 14.1% | 1.06 | -7.7% | 60% |

- Cheap−expensive half-spread: mean +2.43%/quarter, hit rate 60%, t = 1.65, p = 0.120
- Top-third beat its regional benchmark in 67% of quarters

## THA (13 quarterly periods, 2023-03-31 → 2026-06-30)

| Leg | CAGR | Vol (ann.) | Sharpe | Max DD | Hit rate |
|---|---|---|---|---|---|
| top_third | 24.0% | 26.7% | 0.94 | -13.9% | 54% |
| cheap_half | 24.0% | 26.7% | 0.94 | -13.9% | 54% |
| exp_half | 20.2% | 10.1% | 1.90 | -3.4% | 92% |
| benchmark | 23.7% | 17.0% | 1.35 | -6.4% | 69% |

- Cheap−expensive half-spread: mean +1.42%/quarter, hit rate 54%, t = 0.52, p = 0.614
- Top-third beat its regional benchmark in 38% of quarters

## Honest read

With only ~15 quarters per region, no p-value here deserves
much weight in either direction. The half-spread hit rate and its sign are
the most informative numbers; treat them as a directional sanity check on
the signal, not as evidence the strategy 'works'. Known measurement bias:
adjusted prices slightly understate historical P/B levels (see module
docstring) — it affects levels far more than within-region rankings.

## Holdings by quarter

| region   | rebalance_date      | top_third              | cheap_half                     | expensive_half                 |
|:---------|:--------------------|:-----------------------|:-------------------------------|:-------------------------------|
| AUS      | 2022-09-30 00:00:00 | BEN.AX, BOQ.AX         | BEN.AX, BOQ.AX, CBA.AX         | WBC.AX, NAB.AX, JDO.AX         |
| AUS      | 2022-12-30 00:00:00 | ANZ.AX, BEN.AX, BOQ.AX | ANZ.AX, BEN.AX, BOQ.AX         | WBC.AX, CBA.AX, JDO.AX         |
| AUS      | 2023-03-31 00:00:00 | ANZ.AX, BEN.AX, BOQ.AX | ANZ.AX, BEN.AX, BOQ.AX         | WBC.AX, CBA.AX, JDO.AX         |
| AUS      | 2023-06-30 00:00:00 | ANZ.AX, BOQ.AX, BEN.AX | ANZ.AX, BOQ.AX, BEN.AX, MQG.AX | NAB.AX, WBC.AX, CBA.AX, JDO.AX |
| AUS      | 2023-09-29 00:00:00 | BOQ.AX, ANZ.AX, MQG.AX | BOQ.AX, ANZ.AX, MQG.AX, BEN.AX | NAB.AX, WBC.AX, CBA.AX, JDO.AX |
| AUS      | 2023-12-29 00:00:00 | ANZ.AX, MQG.AX, BEN.AX | ANZ.AX, MQG.AX, BEN.AX, WBC.AX | NAB.AX, BOQ.AX, CBA.AX, JDO.AX |
| AUS      | 2024-03-28 00:00:00 | ANZ.AX, MQG.AX, BEN.AX | ANZ.AX, MQG.AX, BEN.AX, NAB.AX | WBC.AX, BOQ.AX, CBA.AX, JDO.AX |
| AUS      | 2024-06-28 00:00:00 | ANZ.AX, MQG.AX, BEN.AX | ANZ.AX, MQG.AX, BEN.AX, BOQ.AX | NAB.AX, WBC.AX, CBA.AX, JDO.AX |
| AUS      | 2024-09-30 00:00:00 | ANZ.AX, BEN.AX, NAB.AX | ANZ.AX, BEN.AX, NAB.AX, BOQ.AX | WBC.AX, MQG.AX, CBA.AX, JDO.AX |
| AUS      | 2024-12-31 00:00:00 | ANZ.AX, BEN.AX, NAB.AX | ANZ.AX, BEN.AX, NAB.AX, BOQ.AX | WBC.AX, MQG.AX, CBA.AX, JDO.AX |
| AUS      | 2025-03-31 00:00:00 | ANZ.AX, BEN.AX, NAB.AX | ANZ.AX, BEN.AX, NAB.AX, MQG.AX | WBC.AX, BOQ.AX, CBA.AX, JDO.AX |
| AUS      | 2025-06-30 00:00:00 | ANZ.AX, BEN.AX, NAB.AX | ANZ.AX, BEN.AX, NAB.AX, WBC.AX | MQG.AX, BOQ.AX, JDO.AX, CBA.AX |
| AUS      | 2025-09-30 00:00:00 | ANZ.AX, NAB.AX, BOQ.AX | ANZ.AX, NAB.AX, BOQ.AX, MQG.AX | WBC.AX, CBA.AX, BEN.AX, JDO.AX |
| AUS      | 2025-12-31 00:00:00 | ANZ.AX, BOQ.AX, MQG.AX | ANZ.AX, BOQ.AX, MQG.AX, NAB.AX | WBC.AX, BEN.AX, CBA.AX, JDO.AX |
| AUS      | 2026-03-31 00:00:00 | ANZ.AX, NAB.AX, MQG.AX | ANZ.AX, NAB.AX, MQG.AX, BOQ.AX | BEN.AX, WBC.AX, JDO.AX, CBA.AX |
| THA      | 2023-03-31 00:00:00 | KKP.BK, KTB.BK, BAY.BK | KKP.BK, KTB.BK, BAY.BK         | KBANK.BK, TTB.BK, BBL.BK       |
| THA      | 2023-06-30 00:00:00 | KKP.BK, BAY.BK, KTB.BK | KKP.BK, BAY.BK, KTB.BK         | KBANK.BK, TTB.BK, BBL.BK       |
| THA      | 2023-09-29 00:00:00 | KKP.BK, KTB.BK, BAY.BK | KKP.BK, KTB.BK, BAY.BK         | KBANK.BK, TTB.BK, BBL.BK       |
| THA      | 2023-12-28 00:00:00 | KKP.BK, BAY.BK, KTB.BK | KKP.BK, BAY.BK, KTB.BK         | KBANK.BK, BBL.BK, TTB.BK       |
| THA      | 2024-03-29 00:00:00 | KKP.BK, BAY.BK, KTB.BK | KKP.BK, BAY.BK, KTB.BK         | KBANK.BK, BBL.BK, TTB.BK       |
| THA      | 2024-06-28 00:00:00 | KKP.BK, BAY.BK, KTB.BK | KKP.BK, BAY.BK, KTB.BK         | KBANK.BK, TISCO.BK, TTB.BK     |
| THA      | 2024-09-30 00:00:00 | KKP.BK, BAY.BK, KTB.BK | KKP.BK, BAY.BK, KTB.BK         | TISCO.BK, KBANK.BK, TTB.BK     |
| THA      | 2024-12-30 00:00:00 | BAY.BK, KKP.BK, KTB.BK | BAY.BK, KKP.BK, KTB.BK         | TISCO.BK, KBANK.BK, TTB.BK     |
| THA      | 2025-03-31 00:00:00 | BAY.BK, KKP.BK, KTB.BK | BAY.BK, KKP.BK, KTB.BK         | KBANK.BK, TISCO.BK, TTB.BK     |
| THA      | 2025-06-30 00:00:00 | BAY.BK, KKP.BK, KTB.BK | BAY.BK, KKP.BK, KTB.BK         | KBANK.BK, TISCO.BK, TTB.BK     |
| THA      | 2025-09-30 00:00:00 | BAY.BK, KKP.BK, KTB.BK | BAY.BK, KKP.BK, KTB.BK         | KBANK.BK, TISCO.BK, TTB.BK     |
| THA      | 2025-12-30 00:00:00 | BAY.BK, BBL.BK, KKP.BK | BAY.BK, BBL.BK, KKP.BK         | TISCO.BK, KBANK.BK, TTB.BK     |
| THA      | 2026-03-31 00:00:00 | BAY.BK, BBL.BK, KKP.BK | BAY.BK, BBL.BK, KKP.BK         | KTB.BK, TISCO.BK, TTB.BK       |