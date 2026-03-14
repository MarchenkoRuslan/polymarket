const BASE = '/api/v1';

const MAX_RETRIES = 3;
const BASE_DELAY = 1000;

async function request(path, params = {}) {
    const url = new URL(BASE + path, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });

    let lastError;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
            const res = await fetch(url.toString());
            if (res.ok) return res.json();
            if (res.status >= 400 && res.status < 500) {
                throw new Error(`API ${res.status}: ${res.statusText}`);
            }
            lastError = new Error(`API ${res.status}: ${res.statusText}`);
        } catch (err) {
            lastError = err;
            if (err.message.startsWith('API 4')) throw err;
        }
        if (attempt < MAX_RETRIES) {
            await sleep(BASE_DELAY * Math.pow(2, attempt));
        }
    }
    throw lastError;
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

export const api = {
    getStatus()                          { return request('/status'); },
    getAnalytics()                       { return request('/analytics'); },
    getMarkets(limit = 100, offset = 0, withSignals = false) {
        return request('/markets', { limit, offset, with_signals: withSignals || undefined });
    },
    getMarket(id)                        { return request(`/markets/${encodeURIComponent(id)}`); },
    getTrades(marketId, limit = 100)     { return request('/trades', { market_id: marketId, limit }); },
    getOrderbook(marketId, limit = 100)  { return request('/orderbook', { market_id: marketId, limit }); },
    getSignals(marketId, limit = 100)    { return request('/signals', { market_id: marketId, limit }); },
    getFeatures(marketId, limit = 500)   { return request('/features', { market_id: marketId, limit }); },
    getNews(limit = 30)                  { return request('/news', { limit }); },
    getResults(marketId, limit = 200)    { return request('/results', { market_id: marketId, limit }); },
};
