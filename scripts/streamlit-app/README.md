# Env Extractor

**Stop typing temp / humidity / CO2 / pH / EC into spreadsheets. Photograph it, click EXTRACT, done.**

A self-hosted app that reads your cultivation logs — TrolMaster screens, Anderson / Infinium zone overview tables, and handwritten paper sheets — and exports clean, flagged data to CSV / JSON / Excel.

- Runs entirely on your computer. No cloud, no telemetry, no account.
- You bring your own Anthropic Claude API key.
- One double-click to launch. Mac or Windows.

---

## 30-second quickstart

1. **Install Python 3.10 or newer** (skip if you already have it).
   - Mac: download from [python.org/downloads](https://www.python.org/downloads/) and run the installer.
   - Windows: same link, but **tick "Add Python to PATH"** during install.

2. **Double-click the launcher**:
   - Mac: `scripts/run.command`
   - Windows: `scripts/run.bat`

   First launch installs the dependencies (about 30 seconds). After that it boots in 3–5 seconds.

3. **Browser opens to `localhost:8501`**. Paste your Anthropic API key in the Settings tab (one-time), then go to Extract and drop in screenshots.

That's it.

---

## What it reads

- **TrolMaster HCS-1 screens** (the green-on-black controller display)
- **Zone Overview tables** (Anderson / Infinium grid layout)
- **Handwritten log sheets** (date columns + IN / S1 / S2 / S3 runoff readings)

It pulls: temperature, humidity, CO2, pH (per channel), EC (per channel), VWC where present. It flags out-of-range readings automatically based on the thresholds you configure.

---

## Configure your facility

First-time setup runs a 3-step wizard. After that, you can edit anything in the **Configure** tab.

- **Buildings & rooms**: add as many buildings as you have. Each building gets a code (`AB`, `EF`, `GH`, whatever) and a list of room numbers. The room label template tells the AI what your controller calls those zones — e.g. `AB Flower {n}` becomes `AB Flower 1`, `AB Flower 2`, etc.
- **Thresholds**: pH and EC red-lines for flagging. Defaults are calibrated for typical flower-stage runoff in coco / rockwool.
- **Units**: Fahrenheit or Celsius. CO2 in ppm.

Hit **Save config**. The Extract tab will use the new settings on the next run.

*(Screenshot placeholder — `docs/img/configure-tab.png`)*

---

## Common config mistakes

- **Empty buildings list.** Add at least one building or the Extract tab will warn you.
- **Room template missing `{n}`.** That's the placeholder for the room number. Without it, every room gets the same name.
- **Threshold high < low.** The app won't stop you, but flagging will misbehave. Double-check.

---

## What's my Claude API key going to cost me?

Rough math (May 2026 pricing):
- One screenshot extraction = ~1500–3000 input tokens + ~200 output tokens.
- At Claude Sonnet 4.6 rates ($3 / 1M input, $15 / 1M output), that's about **$0.008 per extraction**.
- 100 extractions per week = ~$3.50 / month.
- A full daily 24-room sweep (3 buildings x 8 rooms) is roughly **$0.20–0.30 per day**.

The compression slider in the Settings tab lets you trade image quality for tokens — drop max-width to 700px if you want to halve the cost.

---

## Troubleshooting

**"Python not found" when I double-click run.command**
Install Python 3.10+ from [python.org/downloads](https://www.python.org/downloads/). On Windows, tick the "Add Python to PATH" box during install. Then double-click again.

**Mac says "run.command can't be opened because it's from an unidentified developer"**
Right-click the file -> Open -> Open. macOS will let you launch it from then on. (Or: System Settings -> Privacy & Security -> Open Anyway.)

**API key invalid / 401 error**
Check that your key starts with `sk-ant-` and that your Anthropic account has credit on it. Paste it again in Settings, then click Save key.

**"Couldn't read that image"**
Use PNG or JPG. If it's HEIC (iPhone default), open it in Preview / Photos and export as JPG first. Aim for the controller screen filling at least 60% of the frame.

**Extraction returns gibberish or wrong room IDs**
Two fixes: (1) check the Configure tab — does your room label template match what's actually printed on the controller? (2) For TrolMaster single-room shots, fill in the **Room ID override** field on the Extract tab so the AI doesn't have to guess.

**It's slow**
First extraction is always slowest (~10–20s). Subsequent ones are 5–10s. If it's consistently >30s, you might be on a slow connection, or your image is huge — try the compression slider in Settings.

---

## Refund / support

Bought this on Gumroad and it doesn't work? Email **max2k03@gmail.com** with a screenshot of the error. Refunds within 14 days, no questions asked.

Want a feature? Same address. I read everything.

---

## Power users

The Streamlit app is the friendly version. The repo also ships with the original React + Express stack at `artifacts/env-extractor` and `artifacts/api-server` for anyone who wants to host a multi-user web service. That path requires Node, pnpm, and an env var with your Anthropic key. Most growers should stick with the Streamlit app — it's faster to launch and harder to mess up.
