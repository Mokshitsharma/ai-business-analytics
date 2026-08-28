"""
Generate mock business datasets for testing the analytics pipeline.

Run:  python scripts/generate_mock_data.py
Writes CSV files into data/samples/.
"""

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
OUT_DIR = Path("data/samples")


def customer_churn(n: int = 1200) -> pd.DataFrame:
    """Classification target: `churned` (0/1)."""
    plans = RNG.choice(["Basic", "Pro", "Enterprise"], size=n, p=[0.55, 0.35, 0.10])
    regions = RNG.choice(["North", "South", "East", "West"], size=n)
    tenure_months = RNG.integers(1, 60, size=n)
    monthly_spend = RNG.normal(80, 30, size=n).clip(5, 400).round(2)
    support_tickets = RNG.poisson(1.5, size=n)
    logins_last_30d = RNG.poisson(12, size=n)
    contract_type = RNG.choice(["Monthly", "Annual"], size=n, p=[0.7, 0.3])

    # Churn probability driven by a few signals + noise.
    logit = (
        -1.4
        + 0.9 * (contract_type == "Monthly")
        + 0.5 * (support_tickets >= 3)
        + 0.7 * (logins_last_30d < 4)
        - 0.03 * tenure_months
        + 0.010 * (monthly_spend - 80)
        + RNG.normal(0, 0.5, size=n)
    )
    churn_prob = 1 / (1 + np.exp(-logit))
    churned = (RNG.random(n) < churn_prob).astype(int)

    df = pd.DataFrame(
        {
            "customer_id": np.arange(1, n + 1),
            "plan": plans,
            "region": regions,
            "contract_type": contract_type,
            "tenure_months": tenure_months,
            "monthly_spend": monthly_spend,
            "support_tickets": support_tickets,
            "logins_last_30d": logins_last_30d,
            "churned": churned,
        }
    )

    # Inject some missing values so the cleaner has something to do.
    miss_idx = RNG.choice(n, size=int(n * 0.04), replace=False)
    df.loc[miss_idx, "monthly_spend"] = np.nan
    miss_idx2 = RNG.choice(n, size=int(n * 0.03), replace=False)
    df.loc[miss_idx2, "region"] = np.nan

    return df


def monthly_sales(n: int = 900) -> pd.DataFrame:
    """Regression target: `revenue`."""
    start = pd.Timestamp("2023-01-01")
    dates = start + pd.to_timedelta(RNG.integers(0, 600, size=n), unit="D")
    categories = RNG.choice(
        ["Electronics", "Apparel", "Home", "Grocery", "Toys"], size=n
    )
    channel = RNG.choice(["Online", "Retail", "Wholesale"], size=n, p=[0.5, 0.35, 0.15])
    units_sold = RNG.integers(10, 500, size=n)
    unit_price = RNG.normal(25, 10, size=n).clip(3, 120).round(2)
    marketing_spend = RNG.normal(500, 200, size=n).clip(0, 2000).round(2)
    discount_pct = RNG.choice([0, 5, 10, 15, 20], size=n, p=[0.4, 0.25, 0.2, 0.1, 0.05])

    day_of_year = np.asarray(pd.DatetimeIndex(dates).dayofyear, dtype=float)
    base = units_sold * unit_price * (1 - discount_pct / 100)
    seasonal = 1 + 0.15 * np.sin(2 * np.pi * day_of_year / 365.25)
    revenue = (
        base * seasonal
        + 0.8 * marketing_spend
        + RNG.normal(0, 300, size=n)
    ).clip(0).round(2)

    return pd.DataFrame(
        {
            "order_date": dates,
            "category": categories,
            "channel": channel,
            "units_sold": units_sold,
            "unit_price": unit_price,
            "discount_pct": discount_pct,
            "marketing_spend": marketing_spend,
            "revenue": revenue,
        }
    )


def tiny_iris_like(n: int = 30) -> pd.DataFrame:
    """Very small classification set - exercises the safe-CV / small-data paths."""
    species = RNG.choice(["A", "B", "C"], size=n)
    f1 = RNG.normal(5, 1, size=n).round(2)
    f2 = RNG.normal(3, 0.5, size=n).round(2)
    f3 = RNG.normal(1.5, 0.4, size=n).round(2)
    return pd.DataFrame(
        {"feature_1": f1, "feature_2": f2, "feature_3": f3, "species": species}
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    datasets = {
        "customer_churn.csv": customer_churn(),
        "monthly_sales.csv": monthly_sales(),
        "tiny_classification.csv": tiny_iris_like(),
    }

    for name, df in datasets.items():
        path = OUT_DIR / name
        df.to_csv(path, index=False)
        print(f"wrote {path}  ({len(df)} rows, {len(df.columns)} cols)")


if __name__ == "__main__":
    main()
