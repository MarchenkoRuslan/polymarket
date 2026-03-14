const BASE = '/api/v1';

async function request(path, params = {}) {
    const url = new URL(path, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
    const res = await fetch(url.toString());
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
}

export const api = {
    getStatus()                          { return request(`${BASE}/status`); },
    getAnalytics()                       { return request(`${BASE}/analytics`); },
    getMarkets(limit = 100, offset = 0, withSignals = false) {
        return request(`${BASE}/markets`, { limit, offset, with_signals: withSignals || undefined });
    },
    getMarket(id)                        { return request(`${BASE}/markets/${encodeURIComponent(id)}`); },
    getTrades(marketId, limit = 100)     { return request(`${BASE}/trades`, { market_id: marketId, limit }); },
    getOrderbook(marketId, limit = 100)  { return request(`${BASE}/orderbook`, { market_id: marketId, limit }); },
    getSignals(marketId, limit = 100)    { return request(`${BASE}/signals`, { market_id: marketId, limit }); },
    getFeatures(marketId, limit = 500)   { return request(`${BASE}/features`, { market_id: marketId, limit }); },
    getNews(limit = 30)                  { return request(`${BASE}/news`, { limit }); },
    getResults(marketId, limit = 200)    { return request(`${BASE}/results`, { market_id: marketId, limit }); },
};
