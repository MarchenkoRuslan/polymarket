import { api } from '../api.js';
import { formatPrice, formatNumber, signalBadge, truncate, showLoading, showEmpty, showError } from '../utils.js';
import { navigate } from '../router.js';

const PAGE_SIZE = 20;
let _offset = 0;
let _filter = '';

export async function render(container) {
    _offset = 0;
    _filter = '';

    container.innerHTML = `
        <div class="screen">
            <div class="screen-title">Markets</div>
            <div class="search-bar">
                <span class="search-icon">🔍</span>
                <input class="search-input" id="market-search" type="text" placeholder="Search markets…" autocomplete="off"/>
            </div>
            <div id="markets-list"></div>
            <div id="markets-more" style="padding:12px 0"></div>
        </div>`;

    const searchInput = container.querySelector('#market-search');
    let debounce = null;
    searchInput.addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
            _filter = searchInput.value.trim().toLowerCase();
            _offset = 0;
            _loadMarkets(container, false);
        }, 300);
    });

    await _loadMarkets(container, false);
}

async function _loadMarkets(container, append) {
    const listEl = container.querySelector('#markets-list');
    const moreEl = container.querySelector('#markets-more');

    if (!append) {
        showLoading(listEl);
        moreEl.innerHTML = '';
    }

    try {
        const [marketsData, analyticsData] = await Promise.all([
            api.getMarkets(200, 0, false),
            api.getAnalytics().catch(() => null),
        ]);

        const signalsData = await api.getSignals(undefined, 500).catch(() => ({ items: [] }));

        const latestSignals = {};
        (signalsData.items || []).forEach(s => {
            if (!latestSignals[s.market_id] || s.ts > latestSignals[s.market_id].ts) {
                latestSignals[s.market_id] = s;
            }
        });

        const volumeMap = {};
        const priceMap = {};
        (analyticsData?.trade_stats || []).forEach(t => {
            volumeMap[t.market_id] = t.total_volume;
            priceMap[t.market_id] = t.avg_price;
        });

        let items = marketsData.items || [];
        if (_filter) {
            items = items.filter(m =>
                (m.question || '').toLowerCase().includes(_filter) ||
                (m.event || '').toLowerCase().includes(_filter) ||
                m.market_id.toLowerCase().includes(_filter)
            );
        }

        items.sort((a, b) => (volumeMap[b.market_id] || 0) - (volumeMap[a.market_id] || 0));

        const page = items.slice(_offset, _offset + PAGE_SIZE);

        if (!append) listEl.innerHTML = '';

        if (page.length === 0 && _offset === 0) {
            showEmpty(listEl, '📊', 'No markets found', _filter ? 'Try a different search' : 'Markets will appear after data collection');
            return;
        }

        page.forEach(m => {
            const sig = latestSignals[m.market_id];
            const card = document.createElement('div');
            card.className = 'market-card';
            card.innerHTML = `
                <div class="market-card-body">
                    <div class="market-card-question">${_esc(truncate(m.question || m.market_id, 70))}</div>
                    <div class="market-card-meta">
                        ${volumeMap[m.market_id] ? `<span>Vol: ${formatNumber(volumeMap[m.market_id])}</span>` : ''}
                        ${sig ? signalBadge(sig.signal_label) : ''}
                        ${m.outcome_settled ? '<span class="badge badge-info">Settled</span>' : ''}
                    </div>
                </div>
                <div class="market-card-right">
                    ${priceMap[m.market_id] != null ? `<div class="market-card-price">${formatPrice(priceMap[m.market_id])}</div>` : ''}
                    <div class="card-chevron">›</div>
                </div>`;
            card.addEventListener('click', () => navigate(`market/${encodeURIComponent(m.market_id)}`));
            listEl.appendChild(card);
        });

        _offset += page.length;

        if (_offset < items.length) {
            moreEl.innerHTML = `<button class="btn btn-secondary" id="btn-load-more">Load more (${items.length - _offset} remaining)</button>`;
            moreEl.querySelector('#btn-load-more').addEventListener('click', () => _loadMarkets(container, true));
        } else {
            moreEl.innerHTML = `<div class="text-center text-secondary" style="font-size:13px;padding:8px">${items.length} market${items.length !== 1 ? 's' : ''}</div>`;
        }
    } catch (err) {
        if (!append) showError(listEl, err.message);
    }
}

function _esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
