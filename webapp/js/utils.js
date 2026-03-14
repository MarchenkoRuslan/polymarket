export function $(sel, root = document) { return root.querySelector(sel); }
export function $$(sel, root = document) { return [...root.querySelectorAll(sel)]; }

export function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
        if (k === 'class') el.className = v;
        else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
        else if (k === 'html') el.innerHTML = v;
        else el.setAttribute(k, v);
    });
    children.flat().forEach(c => {
        if (c == null) return;
        el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return el;
}

export function formatPrice(v) {
    const n = Number(v);
    if (isNaN(n)) return '—';
    return n < 1 ? `${(n * 100).toFixed(1)}¢` : `$${n.toFixed(2)}`;
}

export function formatPnl(v) {
    const n = Number(v);
    if (isNaN(n)) return '—';
    const sign = n >= 0 ? '+' : '';
    return `${sign}$${n.toFixed(2)}`;
}

export function formatNumber(v) {
    const n = Number(v);
    if (isNaN(n)) return '0';
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toLocaleString();
}

export function formatDate(ts) {
    if (!ts) return '—';
    const d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
    if (isNaN(d.getTime())) return String(ts);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function signalBadge(label) {
    const cls = label === 'buy' ? 'badge-buy' : label === 'sell' ? 'badge-sell' : 'badge-hold';
    return `<span class="badge ${cls}">${label}</span>`;
}

export function truncate(str, max = 60) {
    if (!str) return '';
    return str.length > max ? str.slice(0, max) + '…' : str;
}

export function showLoading(container) {
    container.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <span>Loading…</span>
        </div>`;
}

export function showEmpty(container, icon, title, text) {
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">${icon}</div>
            <div class="empty-state-title">${title}</div>
            <div class="empty-state-text">${text}</div>
        </div>`;
}

export function showError(container, msg) {
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">⚠️</div>
            <div class="empty-state-title">Error</div>
            <div class="empty-state-text">${msg}</div>
        </div>`;
}

export function sparklineSVG(prices, width = 64, height = 28) {
    if (!prices || prices.length < 2) return '';
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const pad = 2;
    const w = width - pad * 2;
    const h = height - pad * 2;
    const points = prices.map((p, i) => {
        const x = pad + (i / (prices.length - 1)) * w;
        const y = pad + h - ((p - min) / range) * h;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const last = prices[prices.length - 1];
    const first = prices[0];
    const color = last >= first ? 'var(--positive)' : 'var(--negative)';
    return `<svg class="sparkline" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
