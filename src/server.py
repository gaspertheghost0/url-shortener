from flask import Flask, redirect, abort, render_template_string, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3
import validators
import qrcode
from io import BytesIO
import base64
from datetime import datetime
import secrets
import string
from datetime import timedelta

app = Flask(__name__)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"]
)

DB_FILE = "shortener.db"
TABLE_URLS = "urls"
TABLE_ANALYTICS = "analytics"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔗 Advanced URL Shortener</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3f37c9;
            --success-color: #4cc9f0;
            --danger-color: #f72585;
            --light-color: #f8f9fa;
            --dark-color: #212529;
            --text-color: #2b2d42;
            --text-light: #8d99ae;
            --bg-light: #f4f9ff;
            --bg-dark: #121212;
            --card-dark: #1e1e1e;
        }
        
        body {
            background: var(--bg-light);
            padding-top: 60px;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            color: var(--text-color);
            transition: all 0.3s ease;
        }
        
        body.dark-mode {
            background: var(--bg-dark);
            color: #e0e0e0;
        }
        
        .container {
            max-width: 800px;
            padding-bottom: 2rem;
        }
        
        .card {
            border: none;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s, box-shadow 0.2s;
            margin-bottom: 1.5rem;
        }
        
        body.dark-mode .card {
            background: var(--card-dark);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
        }
        
        .shortcode {
            font-weight: 600;
            color: var(--primary-color);
            text-decoration: none;
        }
        
        body.dark-mode .shortcode {
            color: var(--success-color);
        }
        
        .btn-primary {
            background-color: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .btn-primary:hover {
            background-color: var(--secondary-color);
            border-color: var(--secondary-color);
        }
        
        .btn-toggle-dark {
            position: fixed;
            top: 15px;
            right: 15px;
            z-index: 9999;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .qr-code {
            width: 100px;
            height: 100px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .qr-code:hover {
            transform: scale(1.1);
        }
        
        .stats-badge {
            font-size: 0.75rem;
            background: rgba(108, 117, 125, 0.1);
            border-radius: 4px;
            padding: 2px 6px;
        }
        
        body.dark-mode .stats-badge {
            background: rgba(255, 255, 255, 0.1);
        }
        
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
        }
        
        @media (max-width: 576px) {
            .btn-group-sm {
                flex-direction: column;
                gap: 0.25rem;
            }
            .btn-group-sm .btn {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <button class="btn btn-secondary btn-toggle-dark" onclick="toggleDarkMode()">
        <i class="bi" id="dark-mode-icon"></i>
    </button>
    
    <div class="container">
        <div class="text-center mb-4">
            <h1 class="display-5 fw-bold">🔗 Advanced URL Shortener</h1>
            <p class="lead text-muted">Create, manage, and track your short links</p>
        </div>
        
        <div class="card p-4">
            <h5 class="mb-3"><i class="bi bi-link-45deg me-2"></i>Create New Short Link</h5>
            <form id="create-form" method="post">
                <div class="mb-3">
                    <label for="url" class="form-label">Destination URL</label>
                    <input type="url" name="url" class="form-control" placeholder="https://example.com" required>
                </div>
                <div class="row">
                    <div class="col-md-8 mb-3">
                        <label for="code" class="form-label">Custom Short Code (optional)</label>
                        <input type="text" name="code" class="form-control" placeholder="Leave blank for random">
                    </div>
                    <div class="col-md-4 mb-3">
                        <label for="expiry" class="form-label">Expiration</label>
                        <select name="expiry" class="form-select">
                            <option value="0">No expiration</option>
                            <option value="1">1 day</option>
                            <option value="7">1 week</option>
                            <option value="30">1 month</option>
                            <option value="365">1 year</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary w-100">
                    <i class="bi bi-plus-circle me-2"></i>Create Short Link
                </button>
            </form>
        </div>
        
        <div class="card p-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="mb-0"><i class="bi bi-list-ul me-2"></i>Your Links</h5>
                <div class="d-flex align-items-center">
                    <span class="badge bg-secondary me-2">{{ link_count }} links</span>
                    <button class="btn btn-sm btn-outline-secondary" onclick="refreshStats()">
                        <i class="bi bi-arrow-clockwise"></i>
                    </button>
                </div>
            </div>
            
            {% if links %}
                <div class="list-group" id="links-list">
                    {% for link in links %}
                        <div class="list-group-item" id="link-{{ link.shortcode }}">
                            <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center">
                                <div class="mb-2 mb-md-0" style="flex: 1; min-width: 0;">
                                    <div class="d-flex align-items-center">
                                        <a href="/{{ link.shortcode }}" class="shortcode text-truncate me-2" 
                                           style="display: block; max-width: 150px;" 
                                           title="/{{ link.shortcode }}" data-code="{{ link.shortcode }}">
                                            /{{ link.shortcode }}
                                        </a>
                                        <span class="badge bg-info text-dark">{{ link.clicks }} clicks</span>
                                        {% if link.expires_at and link.expires_at < now %}
                                            <span class="badge bg-danger ms-2">Expired</span>
                                        {% endif %}
                                    </div>
                                    <div class="text-truncate text-muted small" style="max-width: 400px;">
                                        {{ link.original_url }}
                                    </div>
                                    <div class="small mt-1">
                                        <span class="text-muted">Created: {{ link.created_at }}</span>
                                        {% if link.expires_at %}
                                            <span class="text-muted ms-2">Expires: {{ link.expires_at }}</span>
                                        {% endif %}
                                    </div>
                                </div>
                                <div class="d-flex flex-column flex-sm-row align-items-start align-items-md-center gap-2">
                                    <button class="btn btn-sm btn-outline-primary" onclick="copyToClipboard('{{ link.shortcode }}')">
                                        <i class="bi bi-clipboard"></i>
                                    </button>
                                    <button class="btn btn-sm btn-outline-success" onclick="showQR('{{ link.shortcode }}')">
                                        <i class="bi bi-qr-code"></i>
                                    </button>
                                    <button class="btn btn-sm btn-outline-warning" onclick="startEdit('{{ link.shortcode }}')">
                                        <i class="bi bi-pencil"></i>
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger" onclick="deleteLink('{{ link.shortcode }}')">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="text-center py-4">
                    <i class="bi bi-link-45deg text-muted" style="font-size: 2rem;"></i>
                    <p class="text-muted mt-2">No short links created yet</p>
                </div>
            {% endif %}
        </div>
    </div>
    
    <div class="modal fade" id="qrModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">QR Code</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body text-center">
                    <img id="qrImage" src="" class="img-fluid mb-3" style="max-width: 300px;">
                    <div class="input-group mb-3">
                        <input type="text" class="form-control" id="qrLink" readonly>
                        <button class="btn btn-outline-secondary" type="button" onclick="copyQRToClipboard()">
                            <i class="bi bi-clipboard"></i>
                        </button>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <a id="downloadQR" class="btn btn-primary" download="qr-code.png">
                        <i class="bi bi-download me-2"></i>Download
                    </a>
                </div>
            </div>
        </div>
    </div>
    
    <div class="toast align-items-center text-white bg-success" role="alert" aria-live="assertive" aria-atomic="true" id="toast">
        <div class="d-flex">
            <div class="toast-body" id="toast-message"></div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
        
        const toastEl = document.getElementById('toast');
        const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 3000 });
        
        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            const toastMessage = document.getElementById('toast-message');
            
            toastMessage.textContent = message;
            toast.className = `toast align-items-center text-white bg-${type}`;
            
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
        }
        
        function toggleDarkMode() {
            document.body.classList.toggle('dark-mode');
            const icon = document.getElementById('dark-mode-icon');
            
            if (document.body.classList.contains('dark-mode')) {
                localStorage.setItem('dark-mode', 'true');
                icon.className = 'bi bi-sun';
            } else {
                localStorage.setItem('dark-mode', 'false');
                icon.className = 'bi bi-moon';
            }
        }
        
        function applySavedMode() {
            const darkMode = localStorage.getItem('dark-mode') === 'true';
            const icon = document.getElementById('dark-mode-icon');
            
            if (darkMode) {
                document.body.classList.add('dark-mode');
                icon.className = 'bi bi-sun';
            } else {
                icon.className = 'bi bi-moon';
            }
        }
        
        function copyToClipboard(code) {
            const url = `${window.location.origin}/${code}`;
            navigator.clipboard.writeText(url).then(() => {
                showToast('Copied to clipboard!');
            }).catch(err => {
                console.error('Failed to copy: ', err);
                showToast('Failed to copy', 'danger');
            });
        }
        
        function showQR(code) {
            const url = `${window.location.origin}/${code}`;
            const qrImage = document.getElementById('qrImage');
            const qrLink = document.getElementById('qrLink');
            const downloadQR = document.getElementById('downloadQR');
            
            qrImage.src = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(url)}`;
            qrLink.value = url;
            downloadQR.href = qrImage.src;
            
            const modal = new bootstrap.Modal(document.getElementById('qrModal'));
            modal.show();
        }
        
        function copyQRToClipboard() {
            const qrLink = document.getElementById('qrLink');
            qrLink.select();
            document.execCommand('copy');
            showToast('Copied to clipboard!');
        }
        
        async function deleteLink(code) {
            if (!confirm(`Are you sure you want to delete /${code}?`)) return;
            
            try {
                const response = await fetch(`/api/links/${code}`, { 
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    document.getElementById(`link-${code}`).remove();
                    showToast('Link deleted successfully');
                } else {
                    const error = await response.json();
                    showToast(error.error || 'Failed to delete link', 'danger');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Failed to delete link', 'danger');
            }
        }
        
        function startEdit(code) {
            const li = document.getElementById(`link-${code}`);
            const url = li.querySelector('.text-muted').textContent.trim();
            
            li.innerHTML = `
                <div class="mb-3">
                    <label class="form-label">Short Code</label>
                    <input type="text" id="edit-code-${code}" class="form-control" value="${code}">
                </div>
                <div class="mb-3">
                    <label class="form-label">Destination URL</label>
                    <input type="url" id="edit-url-${code}" class="form-control" value="${url}">
                </div>
                <div class="d-flex justify-content-end gap-2">
                    <button class="btn btn-secondary" onclick="cancelEdit('${code}')">Cancel</button>
                    <button class="btn btn-primary" onclick="saveEdit('${code}')">Save Changes</button>
                </div>
            `;
        }
        
        function cancelEdit(code) {
            window.location.reload();
        }
        
        async function saveEdit(oldCode) {
            const newCode = document.getElementById(`edit-code-${oldCode}`).value.trim();
            const newUrl = document.getElementById(`edit-url-${oldCode}`).value.trim();
            
            if (!newCode || !newUrl) {
                showToast('Code and URL cannot be empty', 'danger');
                return;
            }
            
            try {
                const response = await fetch(`/api/links/${oldCode}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        new_code: newCode, 
                        new_url: newUrl 
                    })
                });
                
                if (response.ok) {
                    showToast('Link updated successfully');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    const error = await response.json();
                    showToast(error.error || 'Failed to update link', 'danger');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Failed to update link', 'danger');
            }
        }
        
        async function refreshStats() {
            try {
                const response = await fetch('/api/links');
                if (response.ok) {
                    window.location.reload();
                } else {
                    showToast('Failed to refresh', 'danger');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Failed to refresh', 'danger');
            }
        }
        
        document.getElementById('create-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const url = formData.get('url');
            const code = formData.get('code');
            const expiry = formData.get('expiry');
            
            try {
                const response = await fetch('/api/links', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, code, expiry })
                });
                
                if (response.ok) {
                    showToast('Short link created!');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    const error = await response.json();
                    showToast(error.error || 'Failed to create link', 'danger');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Failed to create link', 'danger');
            }
        });
        
        document.addEventListener('DOMContentLoaded', applySavedMode);
    </script>
</body>
</html>
"""

def ensure_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_URLS} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            shortcode TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NULL,
            clicks INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_ANALYTICS} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shortcode TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            referrer TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shortcode) REFERENCES {TABLE_URLS}(shortcode)
        )
    ''')
    
    cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_shortcode ON {TABLE_URLS}(shortcode)')
    cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_expires ON {TABLE_URLS}(expires_at)')
    cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_analytics_shortcode ON {TABLE_ANALYTICS}(shortcode)')
    
    conn.commit()
    conn.close()

def generate_random_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def validate_url(url):
    if not url:
        return None
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    if not validators.url(url):
        return None
    
    return url

def validate_shortcode(code):
    if not code:
        return None
    
    if not all(c.isalnum() or c in ('-', '_') for c in code):
        return None
    
    return code.lower()

def record_click(shortcode, request):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        UPDATE {TABLE_URLS} 
        SET clicks = clicks + 1 
        WHERE shortcode = ?
    ''', (shortcode,))
    
    cursor.execute(f'''
        INSERT INTO {TABLE_ANALYTICS} 
        (shortcode, ip_address, user_agent, referrer)
        VALUES (?, ?, ?, ?)
    ''', (
        shortcode,
        request.remote_addr,
        request.user_agent.string,
        request.referrer
    ))
    
    conn.commit()
    conn.close()

def get_links():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        SELECT shortcode, original_url, clicks, created_at, expires_at
        FROM {TABLE_URLS}
        ORDER BY created_at DESC
    ''')
    
    links = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for row in cursor.fetchall():
        links.append({
            'shortcode': row[0],
            'original_url': row[1],
            'clicks': row[2],
            'created_at': row[3],
            'expires_at': row[4],
            'is_expired': row[4] and row[4] < now
        })
    
    conn.close()
    return links

def generate_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@app.route("/")
def home():
    ensure_tables()
    links = get_links()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template_string(
        HTML_TEMPLATE,
        links=links,
        link_count=len(links),
        now=now
    )

@app.route("/<code>")
def redirect_short_url(code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        SELECT original_url, expires_at 
        FROM {TABLE_URLS} 
        WHERE shortcode = ?
    ''', (code,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        abort(404)
    
    url, expires_at = row
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if expires_at and expires_at < now:
        abort(410)
    
    record_click(code, request)
    return redirect(url)

@app.route("/api/links", methods=["GET"])
def api_get_links():
    links = get_links()
    return jsonify(links)

@app.route("/api/links", methods=["POST"])
@limiter.limit("10 per minute")
def api_create_link():
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({"error": "Missing URL"}), 400
    
    url = validate_url(data['url'])
    if not url:
        return jsonify({"error": "Invalid URL"}), 400
    
    code = validate_shortcode(data.get('code')) if data.get('code') else generate_random_code()
    if not code:
        return jsonify({"error": "Invalid short code"}), 400
    
    expiry_days = int(data.get('expiry', 0))
    expires_at = None
    if expiry_days > 0:
        expires_at = (datetime.now() + timedelta(days=expiry_days)).strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f'''
            INSERT INTO {TABLE_URLS} 
            (original_url, shortcode, expires_at)
            VALUES (?, ?, ?)
        ''', (url, code, expires_at))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Short code already exists"}), 409
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
    
    conn.close()
    return jsonify({
        "shortcode": code,
        "url": url,
        "expires_at": expires_at,
        "short_url": f"{request.host_url}{code}"
    }), 201

@app.route("/api/links/<code>", methods=["GET"])
def api_get_link(code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        SELECT original_url, created_at, expires_at, clicks
        FROM {TABLE_URLS}
        WHERE shortcode = ?
    ''', (code,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Not found"}), 404
    
    return jsonify({
        "shortcode": code,
        "url": row[0],
        "created_at": row[1],
        "expires_at": row[2],
        "clicks": row[3],
        "short_url": f"{request.host_url}{code}",
        "qr_code": f"{request.host_url}api/qr/{code}"
    })

@app.route("/api/links/<code>", methods=["PUT"])
@limiter.limit("10 per minute")
def api_update_link(code):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    new_code = validate_shortcode(data.get('new_code'))
    new_url = validate_url(data.get('new_url'))
    
    if new_url is None:
        return jsonify({"error": "Invalid URL"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        if new_code and new_code != code:
            cursor.execute(f'''
                SELECT 1 FROM {TABLE_URLS} 
                WHERE shortcode = ?
            ''', (new_code,))
            if cursor.fetchone():
                conn.close()
                return jsonify({"error": "Short code already exists"}), 409
        
        cursor.execute(f'''
            UPDATE {TABLE_URLS}
            SET original_url = COALESCE(?, original_url),
                shortcode = COALESCE(?, shortcode)
            WHERE shortcode = ?
        ''', (new_url, new_code, code))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"error": "Not found"}), 404
        
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
    
    conn.close()
    return jsonify({"message": "Link updated successfully"})

@app.route("/api/links/<code>", methods=["DELETE"])
@limiter.limit("10 per minute")
def api_delete_link(code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        DELETE FROM {TABLE_URLS}
        WHERE shortcode = ?
    ''', (code,))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    
    conn.commit()
    conn.close()
    return jsonify({"message": "Link deleted successfully"})

@app.route("/api/qr/<code>", methods=["GET"])
def api_get_qr_code(code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        SELECT original_url 
        FROM {TABLE_URLS} 
        WHERE shortcode = ?
    ''', (code,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        abort(404)
    
    short_url = f"{request.host_url}{code}"
    qr_code = generate_qr_code(short_url)
    
    return jsonify({
        "shortcode": code,
        "url": row[0],
        "short_url": short_url,
        "qr_code": f"data:image/png;base64,{qr_code}"
    })

@app.route("/api/analytics/<code>", methods=["GET"])
def api_get_analytics(code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        SELECT original_url, created_at, clicks
        FROM {TABLE_URLS}
        WHERE shortcode = ?
    ''', (code,))
    
    link_info = cursor.fetchone()
    if not link_info:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    
    cursor.execute(f'''
        SELECT timestamp, ip_address, user_agent, referrer
        FROM {TABLE_ANALYTICS}
        WHERE shortcode = ?
        ORDER BY timestamp DESC
        LIMIT 100
    ''', (code,))
    
    analytics = []
    for row in cursor.fetchall():
        analytics.append({
            "timestamp": row[0],
            "ip_address": row[1],
            "user_agent": row[2],
            "referrer": row[3]
        })
    
    conn.close()
    
    return jsonify({
        "shortcode": code,
        "url": link_info[0],
        "created_at": link_info[1],
        "total_clicks": link_info[2],
        "recent_clicks": analytics
    })

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(410)
def page_gone(e):
    return jsonify({"error": "This link has expired"}), 410

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded"}), 429

if __name__ == "__main__":
    ensure_tables()
    app.run(debug=True)
