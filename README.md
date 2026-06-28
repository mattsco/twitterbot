# Twitter Growth Bot

> An automated audience-growth engine that scaled a Twitter account to **12,500+ followers** by identifying, scoring, and engaging high-probability follow-back accounts — fully automated, data-driven, and production-deployed.

Built and operated end-to-end by **Mattsco**. Inspired by early work from Simon Robain.

---

## 📈 Impact

- **12,500+ followers** acquired organically through automated, targeted engagement.
- **Predictive targeting** instead of spray-and-pray: a logistic-regression model (**AUC ≈ 0.73**) ranks every candidate account by its probability of following back, so the daily engagement budget is spent only on the highest-value targets.
- **Self-sustaining pipeline**: discovery → enrichment → scoring → action → measurement, running unattended on a schedule.

---

## 🧠 Why it's interesting (the engineering story)

This isn't a one-script hack. It's a small **end-to-end data product** with the same shape as a production ML system:

1. **Data ingestion** — searches Twitter across a rotating sample of hashtags, deduplicates, and pulls structured tweet + author features.
2. **Feature store** — persists every encountered user profile as JSON, merging on re-encounter so the dataset enriches over time.
3. **Modeling** — a logistic-regression scorer (`followers_count`, `friends_count`) estimates follow-back likelihood; candidates are ranked and deduplicated per account.
4. **Action layer** — engages the top-ranked accounts within a configurable daily rate limit, with built-in API timeouts and back-off to respect platform quotas.
5. **Measurement & hygiene** — tracks net new followers each run, logs every action, and runs a rolling cleanup of stale engagements.

It also handles the unglamorous-but-real production concerns: **rate limiting** (pauses and cursored pagination), **timeouts** (`SIGALRM`-based API guards), **idempotent state** (CSV/JSON checkpoints between runs), and **graceful failure** (no single bad API call kills a run).

---

## 🏗️ Architecture

```
Hashtag list ─▶ get_tweet() ──▶ save_twittos()        (discover + enrich)
                    │
                    ▼
             simple_model() ──▶ score()                (rank by P(follow-back))
                    │
                    ▼
             like_tweets()                             (engage top N, rate-limited)
                    │
                    ▼
   followers_won() / delete_like() / delete_old_fav()  (measure + clean up)
```

| Component | Responsibility |
|-----------|----------------|
| `connection_to_twitter()` | Authenticated client from stored API credentials. |
| `callTwitterWithTimeout()` | Timeout-guarded API wrapper (`SIGALRM`) so slow calls fail fast. |
| `get_tweet()` | Discovers candidate tweets across a sampled hashtag set; filters out accounts already followed/engaged. |
| `save_twittos()` | Append/merge user profiles into a JSON feature store. |
| `score()` | Logistic-regression follow-back probability (AUC ≈ 0.73). |
| `simple_model()` | Ranks, dedupes, and prepares candidates for action. |
| `like_tweets()` | Engages top-ranked accounts within the daily limit; logs results. |
| `followers_won()` | Computes net new followers per run and writes reporting. |
| `get_followers()` | Cursored, rate-limited full follower export. |
| `delete_like()` / `delete_old_fav()` | Rolling engagement cleanup. |

---

## 🛠️ Tech stack

- **Python** · **pandas** · **NumPy** — data wrangling and feature engineering
- **birdy** — Twitter API v1.1 client
- **Logistic regression** — lightweight, interpretable follow-back scoring
- **Dataiku DSS** — orchestration, scheduling, managed datasets, and secrets

---

## ⚙️ How it runs

Deployed as a set of scheduled recipes on **Dataiku DSS**. Credentials and runtime parameters live in platform variables (never in code):

| Parameter | Purpose |
|-----------|---------|
| `CONSUMER_KEY` / `CONSUMER_SECRET` | Twitter app credentials |
| `ACCESS_TOKEN` / `ACCESS_TOKEN_SECRET` | Account OAuth tokens |
| `screen_name` | Target account |
| `like_limit` | Daily engagement budget |

Tunable constants: `MAX_QUERY` (hashtags sampled per run), `MAX_USER_RETWEET`, `TIMEOUT` (API guard).

---

## 🔭 Honest context & what I'd do differently today

This project shipped in the **Python 2 / Twitter API v1.1 era** and reflects it — and I think that context is a feature, not a bug, in a portfolio: it shows a real result delivered with the tools of the time. If I rebuilt it today I would:

- Port to **Python 3** and migrate to the **Twitter/X API v2** (`tweepy`).
- **Decouple from Dataiku** so it runs standalone (`.env` config, local/DB storage).
- Replace the hand-rolled scorer with a richer model and proper offline evaluation.
- Re-examine the engagement strategy against current platform policy.

The skills it demonstrates — framing a growth problem as an ML ranking task, building a full ingest-score-act-measure loop, and operating it reliably against a rate-limited external API — are exactly what I bring to data and ML engineering work today.

---

*Archived portfolio project. Built for learning and a real growth result; not maintained for current platform APIs.*
