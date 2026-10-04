import pandas as pd

df = pd.read_csv("All_Diets.csv")

df["Diet_type"] = df["Diet_type"].str.strip().str.title()
df["Cuisine_type"] = df["Cuisine_type"].str.strip().str.lower()

macros = ["Protein(g)", "Carbs(g)", "Fat(g)"]
df[macros] = df[macros].fillna(df[macros].mean())

print("Missed")
print(df.isnull().sum())
print()
print("Diet Types:")
print(df["Diet_type"].unique)
print("Number of Rows:",len(df))