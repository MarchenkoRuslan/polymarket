import { API_BASE_URL } from './config.js';

async function request(path, params = {}) {
    const url = new URL(API_BASE_URL + path);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
    const res = await fetch(url.toString());
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
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
