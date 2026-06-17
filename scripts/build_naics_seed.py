"""Download Census NAICS 2022 codes and convert to dbt seed CSV."""
from pathlib import Path
import requests
import pandas as pd

URL = "https://www.census.gov/naics/2022NAICS/6-digit_2022_Codes.xlsx"
OUTPUT = Path("seeds/naics_codes.csv")

def main() -> None:
    print(f"Downloading {URL}")
    response = requests.get(URL, timeout=30)
    response.raise_for_status()

    temp_xlsx = Path("temp_naics.xlsx")
    temp_xlsx.write_bytes(response.content)

    print("Reading xlsx")
    df = pd.read_excel(temp_xlsx)

    # Inspect actual column names — Census files vary
    print(f"Columns found: {df.columns.tolist()}")
    print(f"Initial shape: {df.shape}")
    print("Sample rows:")
    print(df.head())

    # Common column names in Census files - adjust based on actual output
    # Census typically uses something like "2022 NAICS Code" and "2022 NAICS Title"
    # If different, update the rename below
    rename_map = {
        col: "naics_code" for col in df.columns if "code" in col.lower()
    }
    rename_map.update({
        col: "naics_title" for col in df.columns if "title" in col.lower() or "description" in col.lower()
    })
    df = df.rename(columns=rename_map)

    # Clean and filter to 6-digit codes only
    # Drop rows where naics_code is NaN (header/spacer rows)
    df = df.dropna(subset=["naics_code"])

    # Convert float → int → str to strip the trailing ".0"
    df["naics_code"] = df["naics_code"].astype(int).astype(str).str.strip()
    df["naics_title"] = df["naics_title"].astype(str).str.strip()

    # Filter to 6-digit codes only
    df = df[df["naics_code"].str.match(r"^\d{6}$")]
    df = df[["naics_code", "naics_title"]].drop_duplicates(subset=["naics_code"])

    print(f"Final shape: {df.shape}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    temp_xlsx.unlink()
    print(f"Wrote {len(df)} rows to {OUTPUT}")

if __name__ == "__main__":
    main()