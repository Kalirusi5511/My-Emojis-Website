from flask import Flask, jsonify, render_template, request, send_from_directory
import os
import sys
import json
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import shutil

# ============================================================
# PFADE
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CACHE_DIR = os.path.join(BASE_DIR, 'cache')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
DB_PATH = os.path.join(DATA_DIR, 'emojis.db')
LOG_FILE = os.path.join(LOGS_DIR, 'app.log')
INDEX_FILE = os.path.join(TEMPLATES_DIR, 'index.html')

# ============================================================
# GLOBALE VARIABLEN
# ============================================================
log = None
config = None

# ============================================================
# AUTO-ORDNER ERSTELLEN
# ============================================================
def ensure_directories():
    """Erstellt alle nötigen Ordner automatisch."""
    dirs = {
        'data': DATA_DIR,
        'cache': CACHE_DIR,
        'logs': LOGS_DIR,
        'static': STATIC_DIR,
        'templates': TEMPLATES_DIR,
    }
    
    created = []
    for name, path in dirs.items():
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            created.append(name)
    
    return created


# ============================================================
# AUTO-CONFIG
# ============================================================
DEFAULT_CONFIG = {
    "version": "2.0",
    "app_name": "Emoji Ultra Server",
    "port": 5000,
    "host": "0.0.0.0",
    "debug": False,
    "features": {
        "auto_sync_emojis": True,
        "auto_backup_db": True,
        "enable_search_api": True,
        "enable_stats_api": True,
        "enable_regenerate_api": True,
        "log_requests": True,
        "cache_emojis": True
    },
    "emoji_ranges": [
        [0x1F600, 0x1F64F], [0x1F910, 0x1F92F], [0x1F970, 0x1F97A],
        [0x1F980, 0x1F9A0], [0x1FA70, 0x1FAFF],
        [0x1F440, 0x1F450], [0x1F466, 0x1F478], [0x1F47B, 0x1F47F],
        [0x1F480, 0x1F483], [0x1F485, 0x1F48E], [0x1F590, 0x1F596],
        [0x1F645, 0x1F64F], [0x1F930, 0x1F93A], [0x1F93C, 0x1F93E],
        [0x1F400, 0x1F43F], [0x1F980, 0x1F9AE], [0x1F300, 0x1F320],
        [0x1F324, 0x1F32C], [0x1F330, 0x1F335], [0x1F337, 0x1F37C],
        [0x1F38D, 0x1F3A0], [0x1F3A1, 0x1F3F0],
        [0x1F345, 0x1F37F], [0x1F950, 0x1F96F], [0x1F9C0, 0x1F9CB],
        [0x1F680, 0x1F6A4], [0x1F6B0, 0x1F6B2], [0x1F6E0, 0x1F6EC],
        [0x1F30D, 0x1F32C],
        [0x1F4A0, 0x1F4FF], [0x1F50D, 0x1F52F], [0x1F5A4, 0x1F5FF],
        [0x1F900, 0x1F9FF],
        [0x2600, 0x26FF], [0x2700, 0x27BF], [0x2B00, 0x2BFF],
        [0x1F500, 0x1F5A3]
    ]
}


def ensure_config():
    """Erstellt config.json falls nicht vorhanden."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        return True, DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        
        updated = False
        for key, value in DEFAULT_CONFIG.items():
            if key not in cfg:
                cfg[key] = value
                updated = True
        
        if 'features' not in cfg:
            cfg['features'] = DEFAULT_CONFIG['features'].copy()
            updated = True
        else:
            for key, value in DEFAULT_CONFIG['features'].items():
                if key not in cfg['features']:
                    cfg['features'][key] = value
                    updated = True
        
        if updated:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        
        return False, cfg
    
    except (json.JSONDecodeError, IOError):
        shutil.copy(CONFIG_FILE, CONFIG_FILE + '.backup')
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        return True, DEFAULT_CONFIG.copy()


# ============================================================
# LOGGING SETUP (muss NACH ensure_directories aufgerufen werden!)
# ============================================================
def setup_logging():
    """Richtet Logging mit Rotation ein."""
    logger = logging.getLogger('emoji_server')
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File Handler (Ordner muss existieren!)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# ============================================================
# STATIC FILES
# ============================================================
def ensure_static_files():
    files_created = []
    
    favicon_path = os.path.join(STATIC_DIR, 'favicon.ico')
    if not os.path.exists(favicon_path):
        with open(favicon_path, 'wb') as f:
            f.write(b'\x00\x00\x01\x00\x00\x00')
        files_created.append('favicon.ico')
    
    robots_path = os.path.join(STATIC_DIR, 'robots.txt')
    if not os.path.exists(robots_path):
        with open(robots_path, 'w', encoding='utf-8') as f:
            f.write("User-agent: *\nAllow: /\n")
        files_created.append('robots.txt')
    
    return files_created


# ============================================================
# INDEX.HTML
# ============================================================
DEFAULT_INDEX_HTML = '''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🚀 Emoji Ultra</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0f0f14; --card: #1a1a24; --border: #2a2a3a;
    --accent: #8b5cf6; --accent-2: #ec4899; --success: #10b981;
  }
  html, body {
    background: var(--bg); color: #fff;
    font-family: 'Segoe UI', system-ui, sans-serif;
    padding: 12px; min-height: 100vh;
  }
  h1 {
    text-align: center; font-size: 1.3rem; margin-bottom: 4px;
    background: linear-gradient(90deg, var(--accent), var(--accent-2), #f59e0b);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .info { text-align: center; color: #888; font-size: 0.75rem; margin-bottom: 12px; }
  .stats {
    text-align: center; color: var(--success); font-size: 0.7rem;
    margin-bottom: 8px; font-family: monospace;
  }
  .server-badge {
    text-align: center; font-size: 0.7rem; padding: 4px 8px;
    border-radius: 4px; display: inline-block; margin: 0 auto 8px;
    background: var(--card); color: #888; border: 1px solid var(--border);
  }
  .server-badge.online { color: var(--success); border-color: var(--success); }
  .server-badge.offline { color: #ef4444; border-color: #ef4444; }
  .toolbar {
    display: flex; flex-wrap: wrap; gap: 8px; justify-content: center;
    align-items: center; margin: 12px 0; position: sticky; top: 0;
    background: rgba(15,15,20,0.95); backdrop-filter: blur(10px);
    padding: 10px 0; z-index: 100;
  }
  .search {
    flex: 1; min-width: 200px; max-width: 400px;
    padding: 8px 12px; border-radius: 8px;
    border: 1px solid var(--border); background: var(--card);
    color: #fff; font-size: 0.9rem; outline: none;
  }
  .search:focus { border-color: var(--accent); }
  .size-btn {
    padding: 6px 12px; border-radius: 6px;
    border: 1px solid var(--border); background: var(--card);
    color: #ccc; cursor: pointer; font-size: 0.8rem;
  }
  .size-btn.active { background: var(--accent); color: #fff; border-color: transparent; }
  .counter { text-align: center; color: #666; font-size: 0.75rem; margin-bottom: 10px; }
  .grid-container { max-width: 1400px; margin: 0 auto; padding: 8px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(36px, 1fr));
    gap: 4px;
  }
  .grid.large { grid-template-columns: repeat(auto-fill, minmax(52px, 1fr)); }
  .grid.xl { grid-template-columns: repeat(auto-fill, minmax(68px, 1fr)); }
  .e {
    aspect-ratio: 1; display: flex; align-items: center;
    justify-content: center; font-size: 22px; cursor: pointer;
    border-radius: 6px; user-select: none; line-height: 1;
    transition: transform 0.1s, background 0.1s;
  }
  .grid.large .e { font-size: 34px; }
  .grid.xl .e { font-size: 46px; }
  .e:hover { background: #2a2a3a; transform: scale(1.2); z-index: 10; position: relative; }
  .e:active { transform: scale(1.1); background: var(--accent); }
  .e.copied { background: var(--success) !important; animation: pulse 0.3s; }
  @keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.5); }
    100% { transform: scale(1); }
  }
  .toast {
    position: fixed; bottom: 20px; left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: var(--success); color: #fff;
    padding: 10px 20px; border-radius: 8px;
    font-weight: bold; font-size: 0.9rem;
    opacity: 0; transition: all 0.3s; pointer-events: none; z-index: 1000;
  }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
  .loader {
    position: fixed; inset: 0; background: var(--bg);
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; z-index: 9999; transition: opacity 0.3s;
  }
  .loader.hidden { opacity: 0; pointer-events: none; }
  .loader-spinner {
    width: 50px; height: 50px;
    border: 3px solid var(--border); border-top-color: var(--accent);
    border-radius: 50%; animation: spin 0.8s linear infinite;
  }
  .loader-text { margin-top: 16px; color: #888; font-size: 0.9rem; text-align: center; padding: 0 20px; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<div class="loader" id="loader">
  <div class="loader-spinner"></div>
  <div class="loader-text" id="loaderText">⏳ Verbinde mit Server...</div>
</div>

<h1>🚀 Emoji Ultra</h1>
<p class="info">Emojis aus SQLite-Datenbank (Auto-Sync)</p>

<div style="text-align: center; margin-bottom: 8px;">
  <span class="server-badge" id="serverBadge">🔌 Verbinde...</span>
</div>

<div class="stats" id="stats">Bereit</div>

<div class="toolbar">
  <input type="text" class="search" id="search" placeholder="🔍 Suchen..." autocomplete="off" spellcheck="false">
  <button class="size-btn active" data-size="small">Klein</button>
  <button class="size-btn" data-size="large">Mittel</button>
  <button class="size-btn" data-size="xl">Groß</button>
</div>

<div class="counter" id="counter">⏳ Lade...</div>

<div class="grid-container">
  <div class="grid" id="grid"></div>
</div>

<div class="toast" id="toast">✅ Kopiert!</div>

<script>
const API_EMOJIS = window.location.origin + '/api/emojis';
const STATE = { all: [], filtered: [], rendered: 0, batchSize: 500, isRendering: false, timings: {} };
const $ = (id) => document.getElementById(id);
const now = () => performance.now();
const grid = $('grid'), search = $('search'), counter = $('counter'),
      toast = $('toast'), loader = $('loader'), loaderText = $('loaderText'),
      stats = $('stats'), serverBadge = $('serverBadge');
const sizeBtns = document.querySelectorAll('.size-btn');

function setServerStatus(online, text) {
  serverBadge.textContent = text;
  serverBadge.className = 'server-badge ' + (online ? 'online' : 'offline');
}

async function fetchEmojis() {
  const t0 = now();
  const res = await fetch(API_EMOJIS);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  if (!data.emojis) throw new Error('Kein emojis-Feld');
  STATE.timings.server = (now() - t0).toFixed(1);
  setServerStatus(true, `🟢 Server online (${data.emojis.length} Emojis)`);
  return data.emojis;
}

function renderBatch() {
  if (STATE.isRendering || STATE.rendered >= STATE.filtered.length) return;
  STATE.isRendering = true;
  const t0 = now();
  const start = STATE.rendered;
  const end = Math.min(start + STATE.batchSize, STATE.filtered.length);
  const fragment = document.createDocumentFragment();
  for (let i = start; i < end; i++) {
    const div = document.createElement('div');
    div.className = 'e';
    div.textContent = STATE.filtered[i];
    div.dataset.emoji = STATE.filtered[i];
    fragment.appendChild(div);
  }
  grid.appendChild(fragment);
  STATE.rendered = end;
  STATE.isRendering = false;
  counter.textContent = STATE.rendered >= STATE.filtered.length
    ? `${STATE.filtered.length.toLocaleString()} Emojis komplett`
    : `${STATE.rendered.toLocaleString()} von ${STATE.filtered.length.toLocaleString()} (scrollen)`;
  STATE.timings.render = (now() - t0).toFixed(1);
  updateStats();
  requestAnimationFrame(() => {
    if (window.scrollY + window.innerHeight >= document.body.scrollHeight - 500) renderBatch();
  });
}

function resetAndRender(list) {
  grid.innerHTML = '';
  STATE.filtered = list;
  STATE.rendered = 0;
  renderBatch();
}

window.addEventListener('scroll', () => {
  requestAnimationFrame(() => {
    if (window.scrollY + window.innerHeight >= document.body.scrollHeight - 500) renderBatch();
  });
}, { passive: true });

grid.addEventListener('click', (e) => {
  const t = e.target.closest('.e');
  if (t) copyEmoji(t.dataset.emoji, t);
});

async function copyEmoji(emoji, el) {
  try {
    if (navigator.clipboard) await navigator.clipboard.writeText(emoji);
    else {
      const ta = document.createElement('textarea');
      ta.value = emoji; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta);
    }
    showToast('✅ ' + emoji + ' kopiert!');
    el.classList.add('copied');
    setTimeout(() => el.classList.remove('copied'), 400);
  } catch (e) { alert('Kopieren fehlgeschlagen'); }
}

let toastTimeout;
function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => toast.classList.remove('show'), 1000);
}

sizeBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    sizeBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const s = btn.dataset.size;
    grid.classList.remove('large', 'xl');
    if (s === 'large') grid.classList.add('large');
    if (s === 'xl') grid.classList.add('xl');
  });
});

let searchTimeout;
search.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    const term = search.value.toLowerCase().trim();
    const t0 = now();
    STATE.filtered = !term ? STATE.all : STATE.all.filter(e => {
      const c = e.codePointAt(0);
      return c.toString(16).includes(term) || e.includes(term);
    });
    STATE.timings.filter = (now() - t0).toFixed(1);
    window.scrollTo({ top: 0 });
    resetAndRender(STATE.filtered);
  }, 120);
});

function updateStats() {
  const t = STATE.timings;
  stats.textContent = `⚡ Server: ${t.server || '–'}ms | Render: ${t.render || '–'}ms | Filter: ${t.filter || '–'}ms`;
}

async function init() {
  loaderText.textContent = '🌐 Lade Emojis aus DB...';
  try {
    STATE.all = await fetchEmojis();
    loaderText.textContent = `✅ ${STATE.all.length} Emojis geladen`;
    resetAndRender(STATE.all);
    updateStats();
    setTimeout(() => { loader.classList.add('hidden'); setTimeout(() => loader.remove(), 400); }, 300);
  } catch (err) {
    setServerStatus(false, `🔴 Server offline: ${err.message}`);
    loaderText.textContent = `❌ Fehler: ${err.message}`;
    counter.textContent = 'Fehler beim Laden';
    setTimeout(() => { loader.classList.add('hidden'); setTimeout(() => loader.remove(), 400); }, 1500);
  }
}

init();
</script>
</body>
</html>
'''


def ensure_index_html():
    if not os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_INDEX_HTML)
        return True
    return False


# ============================================================
# FLASK APP (OHNE log = setup_logging() hier!)
# ============================================================
app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR
)


# ============================================================
# DATENBANK
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emojis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code INTEGER UNIQUE NOT NULL,
            emoji TEXT NOT NULL,
            hex TEXT NOT NULL,
            category TEXT DEFAULT 'other',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hex ON emojis(hex)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_emoji ON emojis(emoji)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON emojis(category)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_emoji_count():
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM emojis').fetchone()[0]
    conn.close()
    return count


def get_metadata(key):
    conn = get_db()
    row = conn.execute('SELECT value FROM metadata WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else None


def set_metadata(key, value):
    conn = get_db()
    conn.execute('''
        INSERT INTO metadata (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
    ''', (key, str(value), str(value)))
    conn.commit()
    conn.close()


def save_emojis_to_db(emojis_data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.executemany(
        'INSERT OR IGNORE INTO emojis (code, emoji, hex) VALUES (?, ?, ?)',
        emojis_data
    )
    conn.commit()
    conn.close()


def load_emojis_from_db():
    conn = get_db()
    rows = conn.execute('SELECT emoji FROM emojis ORDER BY code').fetchall()
    conn.close()
    return [row['emoji'] for row in rows]


# ============================================================
# EMOJI-GENERATOR
# ============================================================
def generate_emojis(ranges=None):
    if ranges is None:
        ranges = DEFAULT_CONFIG['emoji_ranges']
    emojis = []
    seen = set()
    for start, end in ranges:
        for code in range(start, end + 1):
            if 0xD800 <= code <= 0xDFFF: continue
            if 0xFE00 <= code <= 0xFE0F: continue
            try:
                emoji = chr(code)
                if emoji in seen: continue
                if not emoji.isprintable(): continue
                seen.add(emoji)
                emojis.append((code, emoji, format(code, 'x')))
            except (ValueError, OverflowError):
                continue
    return emojis


def ensure_emojis_loaded():
    init_db()
    count = get_emoji_count()
    if count > 0:
        if log: log.info(f"✅ {count} Emojis aus DB geladen")
        if config.get('features', {}).get('auto_sync_emojis', True):
            sync_new_emojis()
        return get_emoji_count()
    if log: log.info("📦 Generiere Emojis (erster Start)...")
    emojis = generate_emojis(config.get('emoji_ranges'))
    if log: log.info(f"   → {len(emojis)} Emojis generiert")
    save_emojis_to_db(emojis)
    set_metadata('last_full_sync', datetime.now().isoformat())
    if log: log.info(f"💾 In DB gespeichert: {DB_PATH}")
    return len(emojis)


def sync_new_emojis():
    ranges = config.get('emoji_ranges', DEFAULT_CONFIG['emoji_ranges'])
    conn = get_db()
    existing = set(row['hex'] for row in conn.execute('SELECT hex FROM emojis').fetchall())
    conn.close()
    new_emojis = []
    for start, end in ranges:
        for code in range(start, end + 1):
            if 0xD800 <= code <= 0xDFFF: continue
            if 0xFE00 <= code <= 0xFE0F: continue
            try:
                hex_code = format(code, 'x')
                if hex_code in existing: continue
                emoji = chr(code)
                if not emoji.isprintable(): continue
                new_emojis.append((code, emoji, hex_code))
            except (ValueError, OverflowError):
                continue
    if new_emojis:
        save_emojis_to_db(new_emojis)
        set_metadata('last_sync', datetime.now().isoformat())
        if log: log.info(f"🔄 Auto-Sync: {len(new_emojis)} neue Emojis hinzugefügt")
        return len(new_emojis)
    return 0


# ============================================================
# ROUTES
# ============================================================
@app.before_request
def log_request():
    if log and not request.path.startswith('/static'):
        log.info(f"→ {request.method} {request.path}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/emojis')
def api_emojis():
    emojis = load_emojis_from_db()
    return jsonify({
        'count': len(emojis),
        'emojis': emojis,
        'synced_at': get_metadata('last_sync') or get_metadata('last_full_sync')
    })


@app.route('/api/stats')
def api_stats():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM emojis').fetchone()[0]
    conn.close()
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    return jsonify({
        'total': total,
        'db_path': DB_PATH,
        'db_size_kb': round(db_size / 1024, 2),
        'last_sync': get_metadata('last_sync'),
        'last_full_sync': get_metadata('last_full_sync'),
        'version': config.get('version', 'unknown') if config else 'unknown'
    })


@app.route('/api/search')
def api_search():
    term = request.args.get('q', '').lower().strip()
    if not term:
        return jsonify({'emojis': [], 'count': 0})
    conn = get_db()
    rows = conn.execute(
        'SELECT emoji, hex FROM emojis WHERE hex LIKE ? OR emoji LIKE ? LIMIT 100',
        (f'%{term}%', f'%{term}%')
    ).fetchall()
    conn.close()
    return jsonify({'emojis': [r['emoji'] for r in rows], 'count': len(rows)})


@app.route('/api/regenerate', methods=['POST'])
def api_regenerate():
    try:
        if os.path.exists(DB_PATH):
            backup_path = DB_PATH + f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            shutil.copy(DB_PATH, backup_path)
            if log: log.info(f"💾 Backup: {backup_path}")
            os.remove(DB_PATH)
        emojis = generate_emojis(config.get('emoji_ranges'))
        save_emojis_to_db(emojis)
        set_metadata('last_full_sync', datetime.now().isoformat())
        if log: log.info(f"🔄 Regenerate: {len(emojis)} Emojis")
        return jsonify({'success': True, 'count': len(emojis)})
    except Exception as e:
        if log: log.error(f"❌ Regenerate Fehler: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sync', methods=['POST'])
def api_sync():
    try:
        added = sync_new_emojis()
        return jsonify({'success': True, 'added': added, 'total': get_emoji_count()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health')
def api_health():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'emojis': get_emoji_count(),
        'db_exists': os.path.exists(DB_PATH)
    })


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Nicht gefunden', 'path': request.path}), 404


# ============================================================
# STARTUP
# ============================================================
def startup():
    global log, config
    
    print("=" * 60)
    print("🚀 Emoji Ultra Server v2.0 (Auto-Sync)")
    print("=" * 60)
    
    # 1. WICHTIG: ZUERST Ordner erstellen!
    created = ensure_directories()
    if created:
        print(f"📁 Ordner erstellt: {', '.join(created)}")
    
    # 2. DANN Logging (jetzt existiert logs/)
    log = setup_logging()
    log.info("Server startet...")
    
    # 3. Config
    created, cfg = ensure_config()
    config = cfg
    if created:
        print(f"⚙️  config.json erstellt")
    else:
        print(f"⚙️  config.json geladen")
    
    # 4. Static Files
    static_created = ensure_static_files()
    if static_created:
        print(f"📄 Static erstellt: {', '.join(static_created)}")
    
    # 5. index.html
    if ensure_index_html():
        print(f"📄 templates/index.html erstellt (Standard-Version)")
    
    # 6. DB
    print(f"💾 Datenbank: {DB_PATH}")
    total = ensure_emojis_loaded()
    print(f"📊 {total} Emojis verfügbar")
    
    print(f"📁 Base: {BASE_DIR}")
    print(f"📁 Logs: {LOGS_DIR}")
    print("-" * 60)


if __name__ == '__main__':
    startup()
    app.run(
        host=config.get('host', '0.0.0.0'),
        port=config.get('port', 5000),
        debug=config.get('debug', False)
    )