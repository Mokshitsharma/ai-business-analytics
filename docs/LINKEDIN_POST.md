# LinkedIn post

Copy-paste ready. Replace `[ADD YOUR REPO URL]` in the first comment once the
repo is pushed to GitHub.

---

## Caption (primary)

Most business data never gets analysed properly — not because the insights
aren't there, but because it takes a data scientist, a notebook, and half a day
to dig them out.

So I built something to close that gap.

Upload a spreadsheet, pick the column you care about, and ~30 seconds later you
get back:

• A cleaned dataset + data-quality report
• A trained ML model with honest accuracy numbers (it picks classification vs
  regression for you)
• SHAP explanations of what's actually driving the outcome
• Trend, anomaly and segment insights
• An AI-written executive summary
• The whole thing as an HTML + PDF report

No ML knowledge needed. No setup.

Under the hood: Python, FastAPI with an async job queue, scikit-learn, SHAP,
and an LLM for the summary — with a deterministic fallback so it never
hard-fails when the model API is down.

Right now it runs end-to-end locally. Next up: persistence, hosting, user
accounts + plans, and a proper analysis history. The full roadmap — hosting,
launch, UI design — is in the repo.

What would you want an automated analysis to tell you about YOUR data?
Drop your suggestions in the comments 👇

🔗 GitHub link in the comments.

#MachineLearning #DataScience #Python #BuildInPublic #Analytics

---

## Caption (short alternate)

Spreadsheet in, full ML analysis out — in about 30 seconds.

Upload a CSV, pick a target column, and get back: a cleaned dataset, a trained
model with real accuracy numbers, SHAP explanations of what drives the outcome,
business insights, and an AI-written executive summary — as an HTML + PDF
report. No notebook, no setup.

Built with Python, FastAPI, scikit-learn, SHAP and an LLM (with a safe
fallback). Runs locally today; hosting, accounts and plans are next.

What would you want it to surface from your data? Suggestions welcome below 👇
GitHub link in the comments.

#MachineLearning #DataScience #Python #BuildInPublic

---

## First comment (post this yourself right after publishing)

GitHub: [ADD YOUR REPO URL]

Still early and rough in places — feedback, ideas and PRs all welcome.
Especially curious which model types and which kinds of insight people would
find most useful.

---

## To publish the repo first

```bash
# create a repo on github.com (or: gh repo create <name> --public --source=. --push)
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin master
```

Then paste the URL into the first comment above.
