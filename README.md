# Pet Deal Alert Bot

Watches Slickdeals' own public search RSS feed (an official feature of their
site) for pet-related deals, and posts new Amazon ones to your Telegram
channel with your Associates tracking tag attached automatically. Runs
hourly, for free, without your computer needing to be on.

## Setup (about 30–40 minutes total, one time)

### 1. Create your Telegram channel + bot
1. In Telegram, tap the pencil icon → **New Channel**. Name it something like "Daily Pet Deals". Public or private both work.
2. Message **@BotFather** in Telegram → `/newbot` → follow the prompts → it gives you a **bot token** (looks like `123456:ABC-defGHI...`). Save it.
3. Add that bot to your channel as an **admin** (Channel settings → Administrators → Add Admin → search your bot's username).
4. Get your **chat ID**: if your channel is public, it's just `@yourchannelname`. If private, post any message in the channel, then visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and look for `"chat":{"id":...}`.

### 2. Amazon Associates
1. Sign up at affiliate-program.amazon.com (free).
2. Get your **tracking ID** (looks like `yourname-20`). You can use this immediately — you don't need approval to generate links, only to keep earning past your first 180 days (3 qualifying sales required).

### 3. Put this code on GitHub
1. Create a free GitHub account if you don't have one.
2. Create a new repository, upload these files (or use GitHub's "Add file → Upload files" in the browser, no command line needed).
3. Go to the repo's **Settings → Secrets and variables → Actions → New repository secret**, and add three secrets:
   - `TELEGRAM_BOT_TOKEN` → from step 1.2
   - `TELEGRAM_CHAT_ID` → from step 1.4
   - `AMAZON_TAG` → from step 2.2

### 4. Turn on the public deals page (the "automatic audience" piece)
Every run now also rebuilds a public webpage at `docs/index.html` listing
recent deals, and commits it back to your repo.
1. Repo **Settings → Pages → Source** → choose **Deploy from a branch** →
   branch `main`, folder `/docs` → **Save**.
2. Your page goes live at `https://<your-username>.github.io/<repo-name>/`.
3. This is genuinely passive, but it is not fast: it can take Google
   weeks to months to index and rank a new page. It works alongside the
   channel, not instead of it.

### 5. Turn it on
GitHub will now run `deal_bot.py` automatically every hour, forever, for free.
To test it immediately instead of waiting for the next hour: go to the
**Actions** tab → **Pet Deal Alert Bot** → **Run workflow**.

## Changing the niche
Open `deal_bot.py` and edit the `KEYWORDS` list near the top. It's currently
`["dog", "cat", "pet"]` — swap in whatever niche you want.

## Honest limitations
- Amazon's affiliate cookie window is 24 hours, so this earns on impulse
  buys, not deals someone sits on for a week.
- Some Slickdeals entries link to the Slickdeals discussion page rather than
  straight to Amazon. The bot still posts these (marked "click through to
  find the Amazon link") so your channel stays active, but only direct
  Amazon links carry your tracking tag automatically.
- Income depends entirely on having people in the channel to click the
  links. The bot handles posting and now also builds a public page for
  search engines to find over time, but there's no legitimate way to
  automate the *first* handful of real visitors. Share your channel or
  page link once in 2–3 places you're genuinely part of (a relevant
  subreddit, a Facebook group, friends who have pets) — a one-time task,
  not an ongoing one. Buying followers or auto-posting to unrelated
  communities gets accounts banned and doesn't convert anyway, since bots
  don't buy dog food.
