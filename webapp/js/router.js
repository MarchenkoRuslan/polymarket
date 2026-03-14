import { destroyAllCharts } from './charts.js';

let _container = null;
const _routes = new Map();
let _currentScreen = '';
let _onNavigate = null;

export function initRouter(container, onNavigate) {
    _container = container;
    _onNavigate = onNavigate;
    window.addEventListener('hashchange', () => _handle());
}

export function registerRoute(name, renderFn) {
    _routes.set(name, renderFn);
}

export function navigate(path) {
    window.location.hash = path;
}

export function currentScreen() {
    return _currentScreen;
}

export function startRouter() {
    _handle();
}

function _handle() {
    const hash = window.location.hash.slice(1) || 'home';
    const parts = hash.split('/');
    const screen = parts[0];
    const params = parts.slice(1);

    destroyAllCharts();

    const renderFn = _routes.get(screen);
    if (renderFn) {
        _container.innerHTML = '';
        _currentScreen = screen;
        renderFn(_container, ...params);
    } else {
        const fallback = _routes.get('home');
        if (fallback) {
            _container.innerHTML = '';
            _currentScreen = 'home';
            fallback(_container);
        }
    }

    if (_onNavigate) _onNavigate(screen, params);
}
