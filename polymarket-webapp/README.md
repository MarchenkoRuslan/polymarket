# Polymarket Web App

Telegram Web App (Mini App) dashboard for the Polymarket Trading System.

Mobile-first SPA: market overview, ML signals, performance charts, news — works as a standalone static site or inside Telegram as a Mini App.

## Quick start (local)

```bash
npm install
npm run dev        # http://localhost:3000
```

## Screens

| Screen | Route | Description |
|--------|-------|-------------|
| Home | `#home` | System status, KPIs, top markets, signal summary |
| Markets | `#markets` | Searchable market cards with price/signal/volume |
| Market Detail | `#market/{id}` | Price chart, trading stats, technicals, signal history |
| Signals | `#signals` | Buy/Hold/Sell summary, distribution, per-market bars |
| Performance | `#performance` | Cumulative P&L, profit by market, spread timeline |
| News | `#news` | RSS news cards |

## Configuration

Edit `public/js/config.js` to set the backend API URL:

```js
export const API_BASE_URL = 'https://polymarket-predictor.up.railway.app/api/v1';
```

## Deploy to Railway

1. Create a new project on Railway from this repo
2. Railway auto-detects Node.js via `package.json`
3. Start command: `npm start` (automatic)
4. Set `PORT` env var if needed (Railway does this automatically)

## Deploy to Vercel / Netlify

Set the publish directory to `public/` and no build command is needed.

## Telegram Web App setup

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Set the Web App URL: BotFather → your bot → Bot Settings → Menu Button → set URL to the deployed app
3. The app auto-detects Telegram environment and adapts theme colors

## Tech stack

- Vanilla JS (ES modules, no build step)
- Chart.js 4 (CDN)
- Telegram Web App SDK
- `serve` for static file hosting
