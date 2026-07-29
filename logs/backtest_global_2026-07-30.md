# Global flat-CoE residual income backtest (USD) — 2026-07-30

**Question tested:** ranking ALL banks in the universe together (Australia,
Thailand, Norway, Sweden, Denmark) by residual-income mispricing at an
identical 10% cost of equity, does the global top-third long book beat an
equal-weighted holding of every bank — and how does it compare with the
S&P 500? All returns in USD, so currency moves are included.

**Method:** quarterly rebalance, 90-day publication lag on annual reports,
equal-weighted legs, point-in-time forecasts from the same trajectory-aware
engine as the live model. Valuation ratios are computed in local currency
(P/B is currency-free); only realised returns are USD-converted. Full
contract in the module docstring of `src/backtest_global.py`.

## Results (15 quarterly periods, 2022-09-30 → 2026-06-30)

| Leg | CAGR | Vol (ann.) | Sharpe | Max DD | Hit rate |
|---|---|---|---|---|---|
| STRATEGY (global top-third long) | 28.7% | 20.6% | 1.35 | -6.6% | 80% |
| cheap half | 28.0% | 19.1% | 1.42 | -6.6% | 80% |
| expensive half | 18.6% | 16.0% | 1.16 | -6.3% | 73% |
| benchmark (equal-weight all banks) | 23.4% | 15.5% | 1.46 | -6.8% | 87% |
| S&P 500 | 21.7% | 11.9% | 1.75 | -4.6% | 80% |

- Strategy vs equal-weight bank benchmark: 67% of quarters ahead, mean excess +1.29%/quarter
- Cheap−expensive half-spread: mean +2.13%/quarter, hit rate 60%, t = 0.97, p = 0.347
- Average countries represented in the long book: 2.7 of 5

## Honest read

With 15 quarters, none of these p-values settle anything. Two
structural points matter more than the headline numbers. First, switching
country risk off (flat 10% CoE) mechanically tilts a *global* ranking toward
the cheapest-looking market, so the long book is concentrated by construction
— check the countries column below before reading the result as stock
selection. Second, the equal-weight bank benchmark is the honest comparison;
the S&P 500 line answers a different question (banks vs US equities)
and is included for context only.

## Holdings by quarter

| rebalance_date      | top_third                                          | countries     | expensive_half                                                            |
|:--------------------|:---------------------------------------------------|:--------------|:--------------------------------------------------------------------------|
| 2022-09-30 00:00:00 | BEN.AX, BOQ.AX                                     | AUS           | WBC.AX, NAB.AX, JDO.AX                                                    |
| 2022-12-30 00:00:00 | ANZ.AX, BEN.AX, BOQ.AX                             | AUS           | WBC.AX, CBA.AX, JDO.AX                                                    |
| 2023-03-31 00:00:00 | KKP.BK, KTB.BK, DNB.OL, SEB-A.ST, BAY.BK, TISCO.BK | NOR, SWE, THA | TTB.BK, BOQ.AX, NAB.AX, BBL.BK, WBC.AX, CBA.AX, DANSKE.CO, JDO.AX         |
| 2023-06-30 00:00:00 | KKP.BK, DNB.OL, SEB-A.ST, BAY.BK, KTB.BK, TISCO.BK | NOR, SWE, THA | BEN.AX, MQG.AX, TTB.BK, NAB.AX, BBL.BK, WBC.AX, CBA.AX, DANSKE.CO, JDO.AX |
| 2023-09-29 00:00:00 | KKP.BK, KTB.BK, DNB.OL, BAY.BK, SEB-A.ST, TISCO.BK | NOR, SWE, THA | MQG.AX, BEN.AX, TTB.BK, NAB.AX, WBC.AX, BBL.BK, CBA.AX, JDO.AX, DANSKE.CO |
| 2023-12-29 00:00:00 | KKP.BK, BAY.BK, KTB.BK, DNB.OL, TISCO.BK, SEB-A.ST | NOR, SWE, THA | BEN.AX, WBC.AX, NAB.AX, BBL.BK, TTB.BK, BOQ.AX, CBA.AX, JDO.AX, DANSKE.CO |
| 2024-03-29 00:00:00 | KKP.BK, BAY.BK, KTB.BK, DNB.OL, TISCO.BK, KBANK.BK | NOR, THA      | MQG.AX, BEN.AX, TTB.BK, NAB.AX, WBC.AX, BOQ.AX, CBA.AX, JDO.AX, DANSKE.CO |
| 2024-06-28 00:00:00 | KKP.BK, BAY.BK, KTB.BK, DNB.OL, SEB-A.ST, BBL.BK   | NOR, SWE, THA | ANZ.AX, MQG.AX, BEN.AX, BOQ.AX, NAB.AX, WBC.AX, CBA.AX, DANSKE.CO, JDO.AX |
| 2024-09-30 00:00:00 | KKP.BK, BAY.BK, DNB.OL, SEB-A.ST, KTB.BK, BBL.BK   | NOR, SWE, THA | ANZ.AX, BEN.AX, NAB.AX, BOQ.AX, WBC.AX, MQG.AX, CBA.AX, DANSKE.CO, JDO.AX |
| 2024-12-31 00:00:00 | BAY.BK, KKP.BK, SEB-A.ST, DNB.OL, KTB.BK, BBL.BK   | NOR, SWE, THA | ANZ.AX, BEN.AX, NAB.AX, BOQ.AX, WBC.AX, MQG.AX, DANSKE.CO, CBA.AX, JDO.AX |
| 2025-03-31 00:00:00 | BAY.BK, KKP.BK, SEB-A.ST, KTB.BK, DNB.OL, BBL.BK   | NOR, SWE, THA | ANZ.AX, BEN.AX, DANSKE.CO, NAB.AX, MQG.AX, WBC.AX, BOQ.AX, CBA.AX, JDO.AX |
| 2025-06-30 00:00:00 | BAY.BK, KKP.BK, KTB.BK, BBL.BK, SEB-A.ST, DNB.OL   | NOR, SWE, THA | ANZ.AX, BEN.AX, DANSKE.CO, NAB.AX, WBC.AX, MQG.AX, BOQ.AX, JDO.AX, CBA.AX |
| 2025-09-30 00:00:00 | BAY.BK, DNB.OL, KKP.BK, KTB.BK, BBL.BK, SEB-A.ST   | NOR, SWE, THA | ANZ.AX, DANSKE.CO, NAB.AX, BOQ.AX, MQG.AX, WBC.AX, CBA.AX, BEN.AX, JDO.AX |
| 2025-12-31 00:00:00 | BAY.BK, DNB.OL, SEB-A.ST, BBL.BK, KKP.BK, KTB.BK   | NOR, SWE, THA | ANZ.AX, BOQ.AX, MQG.AX, NAB.AX, DANSKE.CO, WBC.AX, BEN.AX, CBA.AX, JDO.AX |
| 2026-03-31 00:00:00 | BAY.BK, DNB.OL, BBL.BK, SEB-A.ST, KKP.BK, KBANK.BK | NOR, SWE, THA | DANSKE.CO, ANZ.AX, NAB.AX, MQG.AX, BOQ.AX, BEN.AX, WBC.AX, JDO.AX, CBA.AX |

## Buy / sell blotter

13 buys, 7 sells, 6 positions still open at the end. A name is bought when it enters the global top third, held while it stays, and sold at the rebalance date it drops out. Machine-readable: `data/processed/backtest_global_trades.csv`.

| date       | action     | ticker   | country   |   price_usd |   mispricing_at_trade |   rank_at_trade | reason                           |
|:-----------|:-----------|:---------|:----------|------------:|----------------------:|----------------:|:---------------------------------|
| 2022-09-30 | BUY        | BEN.AX   | AUS       |      4.1417 |                0.2375 |               1 | entered global top third         |
| 2022-09-30 | BUY        | BOQ.AX   | AUS       |      3.3287 |               -0.0412 |               2 | entered global top third         |
| 2022-12-30 | BUY        | ANZ.AX   | AUS       |     13.1074 |                0.2591 |               1 | entered global top third         |
| 2023-03-31 | BUY        | KKP.BK   | THA       |      1.4572 |                1.0715 |               1 | entered global top third         |
| 2023-03-31 | BUY        | KTB.BK   | THA       |      0.3787 |                0.7384 |               2 | entered global top third         |
| 2023-03-31 | BUY        | DNB.OL   | NOR       |     13.6391 |                0.7089 |               1 | entered global top third         |
| 2023-03-31 | BUY        | SEB-A.ST | SWE       |      8.4078 |                0.6057 |               1 | entered global top third         |
| 2023-03-31 | BUY        | BAY.BK   | THA       |      0.7479 |                0.5343 |               3 | entered global top third         |
| 2023-03-31 | BUY        | TISCO.BK | THA       |      2.1587 |                0.3982 |               4 | entered global top third         |
| 2023-03-31 | SELL       | ANZ.AX   | AUS       |     12.6107 |                0.2992 |               1 | dropped out of global top third  |
| 2023-03-31 | SELL       | BEN.AX   | AUS       |      4.9019 |                0.0783 |               2 | dropped out of global top third  |
| 2023-03-31 | SELL       | BOQ.AX   | AUS       |      3.5324 |                0.0447 |               3 | dropped out of global top third  |
| 2024-03-29 | BUY        | KBANK.BK | THA       |      2.7795 |                0.2247 |               5 | entered global top third         |
| 2024-03-29 | SELL       | SEB-A.ST | SWE       |     11.9    |                0.1042 |               1 | dropped out of global top third  |
| 2024-06-28 | BUY        | SEB-A.ST | SWE       |     12.8661 |                0.4943 |               1 | entered global top third         |
| 2024-06-28 | BUY        | BBL.BK   | THA       |      3.1332 |                0.3925 |               4 | entered global top third         |
| 2024-06-28 | SELL       | KBANK.BK | THA       |      2.9163 |                0.3616 |               5 | dropped out of global top third  |
| 2024-06-28 | SELL       | TISCO.BK | THA       |      2.231  |                0.2056 |               6 | dropped out of global top third  |
| 2026-03-31 | BUY        | KBANK.BK | THA       |      5.4432 |                0.003  |               4 | entered global top third         |
| 2026-03-31 | SELL       | KTB.BK   | THA       |      0.9977 |               -0.0154 |               5 | dropped out of global top third  |
| 2026-06-30 | STILL HELD | BAY.BK   | THA       |      1.2331 |              nan      |             nan | open position at end of backtest |
| 2026-06-30 | STILL HELD | BBL.BK   | THA       |      5.3985 |              nan      |             nan | open position at end of backtest |
| 2026-06-30 | STILL HELD | DNB.OL   | NOR       |     29.691  |              nan      |             nan | open position at end of backtest |
| 2026-06-30 | STILL HELD | KBANK.BK | THA       |      6.5564 |              nan      |             nan | open position at end of backtest |
| 2026-06-30 | STILL HELD | KKP.BK   | THA       |      3.0226 |              nan      |             nan | open position at end of backtest |
| 2026-06-30 | STILL HELD | SEB-A.ST | SWE       |     19.8683 |              nan      |             nan | open position at end of backtest |

## Position log (every bank, every quarter)

One row per bank per quarter — whether it was owned, its rank and
mispricing at that date, entry/exit price in USD, and the realised
return. This is the full audit trail for why anything was or was not
held. Machine-readable: `data/processed/backtest_global_positions.csv`.

Held positions only (the full table including unheld names is in the CSV):

| rebalance_date   | next_date   | ticker   | country   |   rank |   fair_pb |   actual_pb |   mispricing | in_strategy   | action   |   weight |   price_usd_entry |   price_usd_exit |   period_return |
|:-----------------|:------------|:---------|:----------|-------:|----------:|------------:|-------------:|:--------------|:---------|---------:|------------------:|-----------------:|----------------:|
| 2022-09-30       | 2022-12-30  | BEN.AX   | AUS       |      1 |     0.66  |       0.533 |       0.2375 | True          | BUY      |   0.5    |            4.1417 |           5.4183 |          0.3082 |
| 2022-09-30       | 2022-12-30  | BOQ.AX   | AUS       |      2 |     0.506 |       0.528 |      -0.0412 | True          | BUY      |   0.5    |            3.3287 |           3.7831 |          0.1365 |
| 2022-12-30       | 2023-03-31  | ANZ.AX   | AUS       |      1 |     1.105 |       0.878 |       0.2591 | True          | BUY      |   0.3333 |           13.1074 |          12.6107 |         -0.0379 |
| 2022-12-30       | 2023-03-31  | BEN.AX   | AUS       |      2 |     0.66  |       0.672 |      -0.0173 | True          | HOLD     |   0.3333 |            5.4183 |           4.9019 |         -0.0953 |
| 2022-12-30       | 2023-03-31  | BOQ.AX   | AUS       |      3 |     0.532 |       0.541 |      -0.0174 | True          | HOLD     |   0.3333 |            3.7831 |           3.5324 |         -0.0663 |
| 2023-03-31       | 2023-06-30  | KKP.BK   | THA       |      1 |     1.508 |       0.728 |       1.0715 | True          | BUY      |   0.1667 |            1.4572 |           1.3508 |         -0.073  |
| 2023-03-31       | 2023-06-30  | KTB.BK   | THA       |      2 |     0.834 |       0.48  |       0.7384 | True          | BUY      |   0.1667 |            0.3787 |           0.444  |          0.1723 |
| 2023-03-31       | 2023-06-30  | DNB.OL   | NOR       |      1 |     1.505 |       0.881 |       0.7089 | True          | BUY      |   0.1667 |           13.6391 |          15.069  |          0.1048 |
| 2023-03-31       | 2023-06-30  | SEB-A.ST | SWE       |      1 |     1.447 |       0.901 |       0.6057 | True          | BUY      |   0.1667 |            8.4078 |           8.8768 |          0.0558 |
| 2023-03-31       | 2023-06-30  | BAY.BK   | THA       |      3 |     0.845 |       0.55  |       0.5343 | True          | BUY      |   0.1667 |            0.7479 |           0.7715 |          0.0316 |
| 2023-03-31       | 2023-06-30  | TISCO.BK | THA       |      4 |     1.927 |       1.378 |       0.3982 | True          | BUY      |   0.1667 |            2.1587 |           2.1635 |          0.0023 |
| 2023-06-30       | 2023-09-29  | KKP.BK   | THA       |      1 |     1.508 |       0.705 |       1.1402 | True          | HOLD     |   0.1667 |            1.3508 |           1.2429 |         -0.0799 |
| 2023-06-30       | 2023-09-29  | DNB.OL   | NOR       |      1 |     1.505 |       1.011 |       0.4889 | True          | HOLD     |   0.1667 |           15.069  |          16.2994 |          0.0816 |
| 2023-06-30       | 2023-09-29  | SEB-A.ST | SWE       |      1 |     1.447 |       0.998 |       0.45   | True          | HOLD     |   0.1667 |            8.8768 |           9.6784 |          0.0903 |
| 2023-06-30       | 2023-09-29  | BAY.BK   | THA       |      2 |     0.845 |       0.593 |       0.4245 | True          | HOLD     |   0.1667 |            0.7715 |           0.7731 |          0.0021 |
| 2023-06-30       | 2023-09-29  | KTB.BK   | THA       |      3 |     0.834 |       0.587 |       0.4202 | True          | HOLD     |   0.1667 |            0.444  |           0.4236 |         -0.046  |
| 2023-06-30       | 2023-09-29  | TISCO.BK | THA       |      4 |     1.927 |       1.442 |       0.3361 | True          | HOLD     |   0.1667 |            2.1635 |           2.1887 |          0.0116 |
| 2023-09-29       | 2023-12-29  | KKP.BK   | THA       |      1 |     1.508 |       0.666 |       1.2659 | True          | HOLD     |   0.1667 |            1.2429 |           1.2088 |         -0.0274 |
| 2023-09-29       | 2023-12-29  | KTB.BK   | THA       |      2 |     0.834 |       0.575 |       0.4501 | True          | HOLD     |   0.1667 |            0.4236 |           0.4387 |          0.0356 |
| 2023-09-29       | 2023-12-29  | DNB.OL   | NOR       |      1 |     1.505 |       1.086 |       0.386  | True          | HOLD     |   0.1667 |           16.2994 |          17.2028 |          0.0554 |
| 2023-09-29       | 2023-12-29  | BAY.BK   | THA       |      3 |     0.845 |       0.61  |       0.3847 | True          | HOLD     |   0.1667 |            0.7731 |           0.7474 |         -0.0333 |
| 2023-09-29       | 2023-12-29  | SEB-A.ST | SWE       |      1 |     1.447 |       1.094 |       0.3224 | True          | HOLD     |   0.1667 |            9.6784 |          11.262  |          0.1636 |
| 2023-09-29       | 2023-12-29  | TISCO.BK | THA       |      4 |     1.927 |       1.498 |       0.2866 | True          | HOLD     |   0.1667 |            2.1887 |           2.3642 |          0.0802 |
| 2023-12-29       | 2024-03-29  | KKP.BK   | THA       |      1 |     1.508 |       0.605 |       1.4913 | True          | HOLD     |   0.1667 |            1.2088 |           1.1934 |         -0.0128 |
| 2023-12-29       | 2024-03-29  | BAY.BK   | THA       |      2 |     0.845 |       0.551 |       0.5318 | True          | HOLD     |   0.1667 |            0.7474 |           0.6593 |         -0.1178 |
| 2023-12-29       | 2024-03-29  | KTB.BK   | THA       |      3 |     0.834 |       0.557 |       0.4974 | True          | HOLD     |   0.1667 |            0.4387 |           0.3811 |         -0.1311 |
| 2023-12-29       | 2024-03-29  | DNB.OL   | NOR       |      1 |     1.505 |       1.088 |       0.3834 | True          | HOLD     |   0.1667 |           17.2028 |          16.2163 |         -0.0573 |
| 2023-12-29       | 2024-03-29  | TISCO.BK | THA       |      4 |     1.927 |       1.513 |       0.2737 | True          | HOLD     |   0.1667 |            2.3642 |           2.2178 |         -0.0619 |
| 2023-12-29       | 2024-03-29  | SEB-A.ST | SWE       |      1 |     1.447 |       1.163 |       0.2448 | True          | HOLD     |   0.1667 |           11.262  |          11.9    |          0.0567 |
| 2024-03-29       | 2024-06-28  | KKP.BK   | THA       |      1 |     1.508 |       0.635 |       1.3733 | True          | HOLD     |   0.1667 |            1.1934 |           1.0741 |         -0.0999 |
| 2024-03-29       | 2024-06-28  | BAY.BK   | THA       |      2 |     0.845 |       0.517 |       0.6329 | True          | HOLD     |   0.1667 |            0.6593 |           0.6147 |         -0.0676 |
| 2024-03-29       | 2024-06-28  | KTB.BK   | THA       |      3 |     0.834 |       0.515 |       0.6207 | True          | HOLD     |   0.1667 |            0.3811 |           0.3988 |          0.0464 |
| 2024-03-29       | 2024-06-28  | DNB.OL   | NOR       |      1 |     1.505 |       1.083 |       0.3892 | True          | HOLD     |   0.1667 |           16.2163 |          17.3813 |          0.0718 |
| 2024-03-29       | 2024-06-28  | TISCO.BK | THA       |      4 |     1.927 |       1.509 |       0.2769 | True          | HOLD     |   0.1667 |            2.2178 |           2.231  |          0.0059 |
| 2024-03-29       | 2024-06-28  | KBANK.BK | THA       |      5 |     0.583 |       0.476 |       0.2247 | True          | BUY      |   0.1667 |            2.7795 |           2.9163 |          0.0492 |
| 2024-06-28       | 2024-09-30  | KKP.BK   | THA       |      1 |     1.079 |       0.549 |       0.9649 | True          | HOLD     |   0.1667 |            1.0741 |           1.3783 |          0.2832 |
| 2024-06-28       | 2024-09-30  | BAY.BK   | THA       |      2 |     0.838 |       0.452 |       0.8535 | True          | HOLD     |   0.1667 |            0.6147 |           0.7573 |          0.232  |
| 2024-06-28       | 2024-09-30  | KTB.BK   | THA       |      3 |     0.848 |       0.508 |       0.6677 | True          | HOLD     |   0.1667 |            0.3988 |           0.5469 |          0.3711 |
| 2024-06-28       | 2024-09-30  | DNB.OL   | NOR       |      1 |     1.638 |       1.044 |       0.5697 | True          | HOLD     |   0.1667 |           17.3813 |          18.2286 |          0.0487 |
| 2024-06-28       | 2024-09-30  | SEB-A.ST | SWE       |      1 |     1.909 |       1.277 |       0.4943 | True          | BUY      |   0.1667 |           12.8661 |          13.4477 |          0.0452 |
| 2024-06-28       | 2024-09-30  | BBL.BK   | THA       |      4 |     0.58  |       0.416 |       0.3925 | True          | BUY      |   0.1667 |            3.1332 |           4.1718 |          0.3315 |
| 2024-09-30       | 2024-12-31  | KKP.BK   | THA       |      1 |     1.079 |       0.619 |       0.7428 | True          | HOLD     |   0.1667 |            1.3783 |           1.3504 |         -0.0203 |
| 2024-09-30       | 2024-12-31  | BAY.BK   | THA       |      2 |     0.838 |       0.489 |       0.7124 | True          | HOLD     |   0.1667 |            0.7573 |           0.6727 |         -0.1117 |
| 2024-09-30       | 2024-12-31  | DNB.OL   | NOR       |      1 |     1.638 |       1.077 |       0.5211 | True          | HOLD     |   0.1667 |           18.2286 |          17.6637 |         -0.031  |
| 2024-09-30       | 2024-12-31  | SEB-A.ST | SWE       |      1 |     1.909 |       1.267 |       0.5064 | True          | HOLD     |   0.1667 |           13.4477 |          12.0315 |         -0.1053 |
| 2024-09-30       | 2024-12-31  | KTB.BK   | THA       |      3 |     0.848 |       0.613 |       0.3843 | True          | HOLD     |   0.1667 |            0.5469 |           0.5306 |         -0.0298 |
| 2024-09-30       | 2024-12-31  | BBL.BK   | THA       |      4 |     0.58  |       0.487 |       0.1903 | True          | HOLD     |   0.1667 |            4.1718 |           3.9837 |         -0.0451 |
| 2024-12-31       | 2025-03-31  | BAY.BK   | THA       |      1 |     0.838 |       0.457 |       0.8347 | True          | HOLD     |   0.1667 |            0.6727 |           0.6229 |         -0.074  |
| 2024-12-31       | 2025-03-31  | KKP.BK   | THA       |      2 |     1.079 |       0.637 |       0.6931 | True          | HOLD     |   0.1667 |            1.3504 |           1.401  |          0.0375 |
| 2024-12-31       | 2025-03-31  | SEB-A.ST | SWE       |      1 |     1.909 |       1.236 |       0.5442 | True          | HOLD     |   0.1667 |           12.0315 |          14.3548 |          0.1931 |
| 2024-12-31       | 2025-03-31  | DNB.OL   | NOR       |      1 |     1.638 |       1.129 |       0.4507 | True          | HOLD     |   0.1667 |           17.6637 |          23.2078 |          0.3139 |
| 2024-12-31       | 2025-03-31  | KTB.BK   | THA       |      3 |     0.848 |       0.624 |       0.358  | True          | HOLD     |   0.1667 |            0.5306 |           0.6086 |          0.1469 |
| 2024-12-31       | 2025-03-31  | BBL.BK   | THA       |      4 |     0.58  |       0.489 |       0.1864 | True          | HOLD     |   0.1667 |            3.9837 |           3.8891 |         -0.0238 |
| 2025-03-31       | 2025-06-30  | BAY.BK   | THA       |      1 |     0.75  |       0.398 |       0.886  | True          | HOLD     |   0.1667 |            0.6229 |           0.6128 |         -0.0164 |
| 2025-03-31       | 2025-06-30  | KKP.BK   | THA       |      2 |     0.957 |       0.629 |       0.5217 | True          | HOLD     |   0.1667 |            1.401  |           1.2827 |         -0.0844 |
| 2025-03-31       | 2025-06-30  | SEB-A.ST | SWE       |      1 |     1.808 |       1.256 |       0.4398 | True          | HOLD     |   0.1667 |           14.3548 |          16.3613 |          0.1398 |
| 2025-03-31       | 2025-06-30  | KTB.BK   | THA       |      3 |     0.939 |       0.657 |       0.4291 | True          | HOLD     |   0.1667 |            0.6086 |           0.6016 |         -0.0114 |
| 2025-03-31       | 2025-06-30  | DNB.OL   | NOR       |      1 |     1.795 |       1.274 |       0.4083 | True          | HOLD     |   0.1667 |           23.2078 |          26.0541 |          0.1226 |
| 2025-03-31       | 2025-06-30  | BBL.BK   | THA       |      4 |     0.625 |       0.455 |       0.3745 | True          | HOLD     |   0.1667 |            3.8891 |           4.0025 |          0.0292 |
| 2025-06-30       | 2025-09-30  | BAY.BK   | THA       |      1 |     0.75  |       0.375 |       0.9981 | True          | HOLD     |   0.1667 |            0.6128 |           0.7065 |          0.1531 |
| 2025-06-30       | 2025-09-30  | KKP.BK   | THA       |      2 |     0.957 |       0.553 |       0.7319 | True          | HOLD     |   0.1667 |            1.2827 |           1.7305 |          0.3491 |
| 2025-06-30       | 2025-09-30  | KTB.BK   | THA       |      3 |     0.939 |       0.623 |       0.5064 | True          | HOLD     |   0.1667 |            0.6016 |           0.7097 |          0.1797 |
| 2025-06-30       | 2025-09-30  | BBL.BK   | THA       |      4 |     0.625 |       0.449 |       0.3918 | True          | HOLD     |   0.1667 |            4.0025 |           4.405  |          0.1006 |
| 2025-06-30       | 2025-09-30  | SEB-A.ST | SWE       |      1 |     1.808 |       1.354 |       0.3352 | True          | HOLD     |   0.1667 |           16.3613 |          18.3244 |          0.12   |
| 2025-06-30       | 2025-09-30  | DNB.OL   | NOR       |      1 |     1.795 |       1.374 |       0.3062 | True          | HOLD     |   0.1667 |           26.0541 |          25.6069 |         -0.0172 |
| 2025-09-30       | 2025-12-31  | BAY.BK   | THA       |      1 |     0.75  |       0.427 |       0.7558 | True          | HOLD     |   0.1667 |            0.7065 |           0.7958 |          0.1263 |
| 2025-09-30       | 2025-12-31  | DNB.OL   | NOR       |      1 |     1.795 |       1.339 |       0.3403 | True          | HOLD     |   0.1667 |           25.6069 |          26.4049 |          0.0312 |
| 2025-09-30       | 2025-12-31  | KKP.BK   | THA       |      2 |     0.957 |       0.736 |       0.3007 | True          | HOLD     |   0.1667 |            1.7305 |           2.0391 |          0.1783 |
| 2025-09-30       | 2025-12-31  | KTB.BK   | THA       |      3 |     0.939 |       0.726 |       0.2938 | True          | HOLD     |   0.1667 |            0.7097 |           0.8361 |          0.1781 |
| 2025-09-30       | 2025-12-31  | BBL.BK   | THA       |      4 |     0.625 |       0.488 |       0.2814 | True          | HOLD     |   0.1667 |            4.405  |           5.1013 |          0.1581 |
| 2025-09-30       | 2025-12-31  | SEB-A.ST | SWE       |      1 |     1.808 |       1.508 |       0.1987 | True          | HOLD     |   0.1667 |           18.3244 |          19.9528 |          0.0889 |
| 2025-12-31       | 2026-03-31  | BAY.BK   | THA       |      1 |     0.75  |       0.472 |       0.587  | True          | HOLD     |   0.1667 |            0.7958 |           0.7517 |         -0.0554 |
| 2025-12-31       | 2026-03-31  | DNB.OL   | NOR       |      1 |     1.795 |       1.388 |       0.2927 | True          | HOLD     |   0.1667 |           26.4049 |          29.1524 |          0.104  |
| 2025-12-31       | 2026-03-31  | SEB-A.ST | SWE       |      1 |     1.808 |       1.6   |       0.1299 | True          | HOLD     |   0.1667 |           19.9528 |          18.0286 |         -0.0964 |
| 2025-12-31       | 2026-03-31  | BBL.BK   | THA       |      2 |     0.625 |       0.555 |       0.1264 | True          | HOLD     |   0.1667 |            5.1013 |           4.8264 |         -0.0539 |
| 2025-12-31       | 2026-03-31  | KKP.BK   | THA       |      3 |     0.957 |       0.852 |       0.1238 | True          | HOLD     |   0.1667 |            2.0391 |           2.1878 |          0.0729 |
| 2025-12-31       | 2026-03-31  | KTB.BK   | THA       |      4 |     0.939 |       0.84  |       0.1181 | True          | HOLD     |   0.1667 |            0.8361 |           0.9977 |          0.1933 |
| 2026-03-31       | 2026-06-30  | BAY.BK   | THA       |      1 |     0.723 |       0.438 |       0.6513 | True          | HOLD     |   0.1667 |            0.7517 |           1.2331 |          0.6403 |
| 2026-03-31       | 2026-06-30  | DNB.OL   | NOR       |      1 |     1.755 |       1.404 |       0.2504 | True          | HOLD     |   0.1667 |           29.1524 |          29.691  |          0.0185 |
| 2026-03-31       | 2026-06-30  | BBL.BK   | THA       |      2 |     0.644 |       0.527 |       0.2206 | True          | HOLD     |   0.1667 |            4.8264 |           5.3985 |          0.1185 |
| 2026-03-31       | 2026-06-30  | SEB-A.ST | SWE       |      1 |     1.675 |       1.468 |       0.141  | True          | HOLD     |   0.1667 |           18.0286 |          19.8683 |          0.102  |
| 2026-03-31       | 2026-06-30  | KKP.BK   | THA       |      3 |     0.949 |       0.901 |       0.0534 | True          | HOLD     |   0.1667 |            2.1878 |           3.0226 |          0.3815 |
| 2026-03-31       | 2026-06-30  | KBANK.BK | THA       |      4 |     0.731 |       0.729 |       0.003  | True          | BUY      |   0.1667 |            5.4432 |           6.5564 |          0.2045 |