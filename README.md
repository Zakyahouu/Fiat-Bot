# Fiat Panda Algeria Bot — Setup Guide

## What this bot does

- Checks 15+ URLs every 30 seconds that Fiat Algeria is likely to use for the Panda registration form
- Scans the fiat.dz homepage for any mention of "panda" — even before the form is up
- Sends you a Telegram message the second anything appears
- If AUTO_SUBMIT is True, it also fills and submits the registration form automatically

---

## Setup — do this in order

### 1. Fill in your info in bot.py

Open `bot.py` and edit the `YOUR_INFO` section at the top:

```python
"nom":       "BENALI",          # Your family name — UPPERCASE, French spelling
"prenom":    "Mohamed",         # Your first name
"email":     "you@email.com",
"telephone": "0555000000",      # 05 / 06 / 07 followed by 8 digits
"wilaya":    "09 - Blida",      # Must match EXACTLY — see full list below
"ville":     "Blida",
```

**Important about names:** Use French/Latin characters only. The form does not accept Arabic script.
Examples: `BENALI`, `BOUDIAF`, `MEZIANE`, `KHELIL`

### 2. Wilaya — copy one exactly

```
01 - Adrar          02 - Chlef          03 - Laghouat       04 - Oum El Bouaghi
05 - Batna          06 - Béjaïa         07 - Biskra          08 - Béchar
09 - Blida          10 - Bouira         11 - Tamanrasset     12 - Tébessa
13 - Tlemcen        14 - Tiaret         15 - Tizi Ouzou      16 - Alger
17 - Djelfa         18 - Jijel          19 - Sétif           20 - Saïda
21 - Skikda         22 - Sidi Bel Abbès 23 - Annaba          24 - Guelma
25 - Constantine    26 - Médéa          27 - Mostaganem      28 - M'Sila
29 - Mascara        30 - Ouargla        31 - Oran            32 - El Bayadh
33 - Illizi         34 - Bordj Bou Arréridj  35 - Boumerdès  36 - El Tarf
37 - Tindouf        38 - Tissemsilt     39 - El Oued         40 - Khenchela
41 - Souk Ahras     42 - Tipaza         43 - Mila            44 - Aïn Defla
45 - Naâma          46 - Aïn Témouchent 47 - Ghardaïa        48 - Relizane
49 - Timimoun       50 - Bordj Badji Mokhtar  51 - Ouled Djellal  52 - Béni Abbès
53 - In Salah       54 - In Guezzam     55 - Touggourt       56 - Djanet
57 - El M'Ghair     58 - El Meniaa
```

### 3. Get your Telegram Chat ID

1. Open Telegram and go to your bot: **t.me/fiat_auto_checker_bot**
2. Send `/start`
3. The bot replies with your Chat ID number
4. Paste it into `bot.py`: `CHAT_ID = 123456789`

### 4. Deploy for free on Railway (recommended)

Railway gives 500 free hours/month — enough for 24/7 continuous running.

**Via GitHub (easiest):**
1. Create a free account at [railway.app](https://railway.app)
2. Create a new GitHub repository
3. Upload these 3 files: `bot.py`, `requirements.txt`, `Procfile`
4. On Railway: New Project → Deploy from GitHub repo → select your repo
5. Railway detects Python automatically and starts the bot
6. Done — the bot runs in the cloud with no machine needed

**Via Railway CLI:**
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

### 5. Alternative: Render.com (also free)

1. Create account at [render.com](https://render.com)
2. New → **Background Worker** (not Web Service — important)
3. Connect your GitHub repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `python bot.py`
6. Free plan → Deploy

> Note: Render's free tier may pause after inactivity. Railway is more reliable for 24/7.

### 6. Run locally (if you want to keep it on your machine)

```bash
pip install -r requirements.txt
python bot.py
```

---

## Telegram commands

| Command  | What it does |
|----------|--------------|
| `/start` | Get your Chat ID + confirm bot is alive |
| `/check` | Uptime, total checks done, last check time, next check ETA |
| `/panda` | Last 3 scan reports — what the bot found on each run |

---

## Settings explained

```python
CHECK_INTERVAL_SECONDS = 30   # How often to check. Safe minimum is 15s.

AUTO_SUBMIT = True            # True  = finds form + fills it + submits it
                              # False = finds form + alerts you only
```

---

## How the auto-submit works

Fiat Algeria's inscription pages use **WordPress Contact Form 7** — confirmed
by inspecting the live Doblo inscription form at fiatdz.com.

When the Panda form is detected, the bot:
1. Reads the page to extract all form field names
2. Builds a POST request with your info mapped to those field names
3. Tries the CF7 REST API first (fastest)
4. Falls back to a direct POST if that fails
5. Checks the response for confirmation strings from Fiat DZ's server
6. Sends you a Telegram message with the result either way
7. Always includes the direct link so you can verify or retry manually

---

## Dealer list (for concessionnaire_preference)

```
PA FIAT EL DJAZAIR              SPA STELLANTIS EL DJAZAIR
SARL BENFLIS MOTORS GROUP       SARL CIRTA CARS
SARL GLOBAL AUTO VISION         SARL KHERIF AUTO STAR
SARL EQUINOX AUTO               SARL ZELMAT AUTOMOBILES
SARL BOURBIA AUTOMOBILE         CENTER AUTOMOBILE TOUHAMI
HALIL KOUBA                     HALIL OULED YAICH
... (full list is in bot.py)
```

Leave `concessionnaire_preference` as `"PA FIAT EL DJAZAIR"` if unsure —
that's the main official Fiat Algeria entity.
