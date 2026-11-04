Stage 1: Backend (Person 1, Day 1)
Builds the whole Python API from nothing and gets it running on their own computer.
Create the project folder, Python environment, requirements.txt and host.json.
Load and clean All_Diets.csv: fix text columns, fill missing numbers. Read the local file now; Stage 3 switches it to Blob Storage.
GET /api/health.
GET /api/insights: average macros per diet, recipe counts per diet, correlation table, execution time.
GET /api/recipes: diet filter, search, pagination.
GET /api/clusters: k-means written from scratch with numpy.
Tests for each endpoint, plus flake8 clean.
Write the API section of the README (every endpoint and its JSON).
Finished when: func start runs, all 4 endpoints answer in the browser or Postman, tests pass, and the work is merged to main.
Your screenshots: tests passing, each endpoint answering locally.
Stage 2: Frontend (Person 2, Day 2)
Starts from Stage 1’s merged main and builds the whole dashboard, connected to the local backend.
Page layout and styling to match UI-for-project2.html.
One fetch helper with a single API_URL setting.
Bar chart (average macros).
Pie chart (recipes per diet).
Correlation heatmap.
Scatter chart coloured by cluster.
Search box, diet dropdown, and the Get Insights / Get Recipes / Get Clusters buttons.
Recipe table with Previous/Next pagination.
Execution-time badge, plus an error banner when the API is down.
Finished when: the whole dashboard works against localhost:7071, every button and filter works, and it’s merged to main.
Your screenshots: each chart and each control in use.
Stage 3: Azure + document (Person 3, Day 3)
Starts from Stage 2’s merged main, puts it all in the cloud and writes the document.
Create the resource group, storage account and private container, and upload the CSV.
Create the Function App and set its settings (connection string, container name). Switch the data loading from the local file to Blob Storage.
Deploy the backend and test the live endpoints.
Create the Static Web App, set API_URL to the live Function, deploy the frontend.
Set CORS so only the dashboard’s address can call the API, then click through the whole live site.
Write deploy.sh and teardown.sh.
Take the Azure portal and live-site screenshots for every rubric row.
Write the PDF/Word document: architecture diagram, 1–2 screenshots per rubric row, GitHub link, live URLs, challenges.
Finished when: both live URLs work and the document is done (except the video link).