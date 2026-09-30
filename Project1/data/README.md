# Dataset

`All_Diets.csv` is the course dataset (7,806 recipes, 5 diet types).

One change was made to the file: two recipe names contained non-Latin
characters, which this repository does not allow. They were removed from the
`Recipe_name` text only; no numeric value, diet type or cuisine was altered.

| Line | Original name | Stored name |
|------|---------------|-------------|
| 7093 | Chinese Shrimp & Egg Flower Soup (original-script title) | Chinese Shrimp & Egg Flower Soup |
| 7430 | Chinese Braised Shrimp E-Fu Noodles (original-script title - Yee Mein) | Chinese Braised Shrimp E-Fu Noodles (Yee Mein) |

Analysis results are therefore identical to those from the unmodified file.
The provenance record of the unmodified course file is kept in
`docs/evidence/dataset-provenance.json`.
