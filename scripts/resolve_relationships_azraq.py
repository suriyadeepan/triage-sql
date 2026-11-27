from pathlib import Path
import polars as pl

base = Path("data/raw/azraq")
clients = pl.scan_csv(base / "clients.csv").select("id", "type")

# 1. Inspect ID ranges per client subtype
print(
    clients.group_by("type")
    .agg(
        pl.len().alias("rows"),
        pl.col("id").min().alias("min_id"),
        pl.col("id").max().alias("max_id"),
    )
    .sort("min_id")
    .collect()
)

# 2. Check each candidate against clients.id and break down by subtype
checks = [
    ("collaterals.csv", "owner_id"),
    ("groups_members.csv", "group_id"),
    ("groups_members.csv", "member_id"),
    ("nsg_meetings.csv", "group_id"),
]

for filename, col in checks:
    res = (
        pl.scan_csv(base / filename)
        .select(pl.col(col).alias("id"))
        .unique()
        .join(clients, on="id", how="left")
        .group_by("type")
        .len()
        .sort("len", descending=True)
        .collect()
    )
    print(f"\n=== {filename}:{col} ===")
    print(res)
