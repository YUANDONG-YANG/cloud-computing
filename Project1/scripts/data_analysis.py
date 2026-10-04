import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

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


avg_marcos_df.groupby("Diet_type")[macros].mean()
print("Average macros by diet type:")
print(avg_macros)
print()

top_protein = (df.sort_values("Protein(g)", ascending=False)).groupby("Diet_type").head(5)

print("Top 5 protein-rich recipes per Diet:")
print(top_protein[["Diet_type", "Recipe_name", "Protein(g)"]])
print ()

highest_protein_diet = avg_macros["Protein(g)"].idxmax()
print(top_protein[["Diet with highest average protein:", highest_protein_diet]])
print()

common_cuisines = (df.groupby("Diet_type")["Cuisine_type"]
.agg(lambda x: x.value_counts().idxmax()))
print("Most Common cuisine per diet type:")
print(common_cuisines)
print()

df["Protein_to_Carbs_ratio"] = df["Protein(g)"] / df["Carbs(g)"].replace(0, pd.NA)
df["Carbs_to_Fat_ratio"] = df["Carbs(g)"] / df["Fat(g)"].replace(0, pd.NA)
print(df[["Recipe_name", "Protein_to_Carbs_ratio", "Carbs_to_Fat_ratio"]].head())

#Bar Chart

avg_macros.plot(kind="bar", figsize=(10, 6))
plt.title("Average Macrountrients by Diet Type")
plt.ylabel("Grams")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("bar_avg_macros.png")
plt.close()

# HeatMap

plt.figure(figsize=(8, 6))
sns.heatmap (avg_macros, annot=True, fmt=".1ft", cmap="y1GnBu")
plt.title("Macrountrient Heatmap by Diet Type")
plt.tight_layout()
plt.savefig("heatmap_macros.png")
plt.close()

#Scatter plot

plt.figure(figzise=(12, 6))
sns.scatterplot(data=top_protein, x="Cuisine_type", y="Protein(g)", hue="Diet Type", s=100)
plt.xticks(rotation=45, ha="right")
plt.title("Top 5 Protein-Rich Recipes per Diet by Cuisine")
plt.tight_layout()
plt.savefig("scatter_top_protein.png")
plt.close()

print("Charts saved: bar_avg_macros.png, headmap_macros.png, scatter_top_protein.png")

