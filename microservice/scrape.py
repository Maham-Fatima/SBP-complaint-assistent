import pandas as pd
import json

# Load the CSV file
df = pd.read_csv("muslim_names.csv")

# Drop rows where either Urdu or English name is missing
df = df.dropna(subset=["arabic_name", "english_name"])

# Clean and format names
df["arabic_name"] = df["arabic_name"].astype(str).str.strip()
df["english_name"] = df["english_name"].astype(str).str.title().str.strip()

# Create dictionary manually
urdu_name_dict = {}
for index, row in df.iterrows():
    urdu = row["arabic_name"]
    english = row["english_name"]
    urdu_name_dict[urdu] = english

# ✅ Optional: Save to JSON
with open("urdu_name_dict.json", "w", encoding="utf-8") as f:
    json.dump(urdu_name_dict, f, ensure_ascii=False, indent=2)

# ✅ Check sample
print("🧪 Sample Ayesha:")
for urdu, eng in urdu_name_dict.items():
    if eng == "Ayesha":
        print(f"{urdu} → {eng}")

print(f"✅ Total names in dictionary: {len(urdu_name_dict)}")
