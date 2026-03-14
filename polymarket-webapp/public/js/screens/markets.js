import { api } from '../api.js';
import { formatPrice, formatNumber, signalBadge, truncate, showLoading, showEmpty, showError } from '../utils.js';
import { navigate } from '../router.js';

const PAGE_SIZE = 20;
let _offset = 0;
let _filter = '';
let _cachedItems = null;
let _cachedVolume = {};
let _cachedPrice = {};
let _cachedSignals = {};

export async function render(container) {
    _offset = 0;
    _filter = '';
    _cachedItems = null;

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
            _renderPage(container);
        }, 300);
    });

    await _fetchAndRender(container);
}

async function _fetchAndRender(container) {
    const listEl = container.querySelector('#markets-list');
    showLoading(listEl);

    try {
        const [marketsData, analyticsData, signalsData] = await Promise.all([
            api.getMarkets(200, 0, false),
            api.getAnalytics().catch(() => null),
            api.getSignals(undefined, 500).catch(() => ({ items: [] })),
        ]);

        _cachedSignals = {};
        (signalsData.items || []).forEach(s => {
            if (!_cachedSignals[s.market_id] || s.ts > _cachedSignals[s.market_id].ts) {
                _cachedSignals[s.market_id] = s;
            }
        });

        _cachedVolume = {};
        _cachedPrice = {};
        (analyticsData?.trade_stats || []).forEach(t => {
            _cachedVolume[t.market_id] = t.total_volume;
            _cachedPrice[t.market_id] = t.avg_price;
        });

        _cachedItems = (marketsData.items || []).slice();
        _cachedItems.sort((a, b) => (_cachedVolume[b.market_id] || 0) - (_cachedVolume[a.market_id] || 0));

        _renderPage(container);
    } catch (err) {
        showError(listEl, err.message);
    }
}

function _getFiltered() {
    if (!_cachedItems) return [];
    if (!_filter) return _cachedItems;
    return _cachedItems.filter(m =>
        (m.question || '').toLowerCase().includes(_filter) ||
        (m.event || '').toLowerCase().includes(_filter) ||
        m.market_id.toLowerCase().includes(_filter)
    );
}

function _renderPage(container) {
    const listEl = container.querySelector('#markets-list');
    const moreEl = container.querySelector('#markets-more');
    if (!listEl || !moreEl) return;

    const items = _getFiltered();
    const page = items.slice(0, _offset + PAGE_SIZE);

    listEl.innerHTML = '';

    if (page.length === 0) {
        showEmpty(listEl, '📊', 'No markets found', _filter ? 'Try a different search' : 'Markets will appear after data collection');
        moreEl.innerHTML = '';
        return;
    }

    page.forEach(m => {
        const sig = _cachedSignals[m.market_id];
        const card = document.createElement('div');
        card.className = 'market-card';
        card.innerHTML = `
            <div class="market-card-body">
                <div class="market-card-question">${_esc(truncate(m.question || m.market_id, 70))}</div>
                <div class="market-card-meta">
                    ${_cachedVolume[m.market_id] ? `<span>Vol: ${formatNumber(_cachedVolume[m.market_id])}</span>` : ''}
                    ${sig ? signalBadge(sig.signal_label) : ''}
                    ${m.outcome_settled ? '<span class="badge badge-info">Settled</span>' : ''}
                </div>
            </div>
            <div class="market-card-right">
                ${_cachedPrice[m.market_id] != null ? `<div class="market-card-price">${formatPrice(_cachedPrice[m.market_id])}</div>` : ''}
                <div class="card-chevron">›</div>
            </div>`;
        card.addEventListener('click', () => navigate(`market/${encodeURIComponent(m.market_id)}`));
        listEl.appendChild(card);
    });

    _offset = page.length;

    if (_offset < items.length) {
        moreEl.innerHTML = `<button class="btn btn-secondary" id="btn-load-more">Load more (${items.length - _offset} remaining)</button>`;
        moreEl.querySelector('#btn-load-more').addEventListener('click', () => {
            _offset += PAGE_SIZE;
            _renderPage(container);
        });
    } else {
        moreEl.innerHTML = `<div class="text-center text-secondary" style="font-size:13px;padding:8px">${items.length} market${items.length !== 1 ? 's' : ''}</div>`;
    }
}

function _esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
