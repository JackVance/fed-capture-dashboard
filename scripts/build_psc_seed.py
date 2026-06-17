"""Download GSA PSC October 2020 codes and convert to dbt seed CSV."""
from pathlib import Path
from io import BytesIO
import requests
import pandas as pd

URL = "https://www.acquisition.gov/sites/default/files/manual/PSC%20October%202020.xlsx"
OUTPUT = Path("seeds/psc_codes.csv")

def main() -> None:
    print(f"Downloading {URL}")
    response = requests.get(URL, timeout=30)
    response.raise_for_status()

    print("Reading xlsx from memory")
    # Read directly from bytes — avoids Windows file-lock issues entirely
    df = pd.read_excel(
        BytesIO(response.content),
        sheet_name="PSC as of 10-30-2020",
        header=2,  # Skip title row 0, blank row 1, real headers on row 2
    )

    print(f"Initial shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")

    # Rename to snake_case
    df = df.rename(columns={
        "PSC CODE": "psc_code",
        "PRODUCT AND SERVICE CODE NAME": "psc_name",
        "START DATE": "start_date",
        "END DATE": "end_date",
        "PRODUCT AND SERVICE CODE FULL NAME (DESCRIPTION)": "psc_description_full",
    })

    # Drop rows with missing code
    df = df.dropna(subset=["psc_code"])
    df["psc_code"] = df["psc_code"].astype(str).str.strip()

    # Clean the name field; fall back to the full description if name is missing
    df["psc_name"] = df["psc_name"].astype(str).str.strip()
    df["psc_description_full"] = df["psc_description_full"].astype(str).str.strip()
    df["psc_name"] = df["psc_name"].where(
        df["psc_name"].notna() & (df["psc_name"] != "nan"),
        df["psc_description_full"],
    )

    # Drop revisions: keep most-recent START DATE per code (handles dupes from code re-issues)
    df = df.sort_values("start_date", ascending=False)
    df = df.drop_duplicates(subset=["psc_code"], keep="first")

    # Filter to valid-shape codes (1-4 alphanumeric chars, all uppercase)
    df = df[df["psc_code"].str.match(r"^[A-Z0-9]{1,4}$")]

    # drop rows with nan names (e.g., 1000)
    df = df[df["psc_name"] != "nan"]

    # Final columns — just code and name; dim model will enrich with category/type
    df = df[["psc_code", "psc_name"]].sort_values("psc_code").reset_index(drop=True)

    print(f"Final shape: {df.shape}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT}")

    print("\nSample numeric codes (Products):")
    print(df[df["psc_code"].str.match(r"^\d+$")].head(5).to_string())
    print("\nSample alpha codes (Services):")
    print(df[df["psc_code"].str.match(r"^[A-Z]")].head(5).to_string())

if __name__ == "__main__":
    main()