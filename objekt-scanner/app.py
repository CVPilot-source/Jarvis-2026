"""Objekt-Scanner – Dokumente von Reinigungsobjekten per QR-Code scannen und per E-Mail senden.

Mitarbeiter brauchen kein Konto: Jedes Objekt hat einen eigenen QR-Code (geheimer Link).
"""
import base64
import json
import os
import re
import secrets
import smtplib
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

import qrcode
import qrcode.image.svg
from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template,
                   request, send_file, session, url_for)

from werkzeug.middleware.proxy_fix import ProxyFix

import scanner

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
PDF_DIR = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "scanner.db"

FIRMA = os.environ.get("FIRMA_NAME", "Reinigungsfirma")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
DEFAULT_EMAIL = os.environ.get("MAIL_TO", "")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "365"))
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
SMTP_SSL = os.environ.get("SMTP_SSL", "0") == "1"  # 1 = Port 465 (SSL), sonst STARTTLS

# Angaben für Impressum (§ 5 DDG) und Datenschutzhinweise (Art. 13 DSGVO)
RECHT = {
    "adresse": os.environ.get("FIRMA_ADRESSE", ""),
    "vertreten": os.environ.get("FIRMA_VERTRETEN", ""),
    "kontakt": os.environ.get("FIRMA_KONTAKT", ""),
    "register": os.environ.get("FIRMA_REGISTER", ""),
    "ustid": os.environ.get("FIRMA_USTID", ""),
    "dsb": os.environ.get("DSB_KONTAKT", ""),
    "aufsicht": os.environ.get("AUFSICHTSBEHOERDE", ""),
    "hoster": os.environ.get("HOSTER", "Hetzner Online GmbH, Industriestr. 25, 91710 Gunzenhausen (Rechenzentrum Nürnberg)"),
}
RECHT_FEHLT = [k for k in ("adresse", "vertreten", "kontakt", "dsb") if not RECHT[k]]

DOC_TYPES = {
    "reinigung": "Reinigungsnachweis",
    "stunden": "Stundenzettel",
    "abnahme": "Abnahme Sonderleistung",
}
MAX_PAGES = 15

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # hinter nginx
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)


# ---------------------------------------------------------------- Datenbank

def db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL,
            name TEXT NOT NULL,
            address TEXT DEFAULT '',
            email TEXT DEFAULT '',
            token TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            object_id INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
            doctype TEXT NOT NULL,
            pages INTEGER NOT NULL,
            note TEXT DEFAULT '',
            filename TEXT NOT NULL,
            created_at TEXT NOT NULL,
            email_status TEXT DEFAULT 'offen'
        );
        CREATE INDEX IF NOT EXISTS idx_sub_obj ON submissions(object_id, created_at);
    """)
    conn.commit()
    conn.close()


def new_token() -> str:
    return secrets.token_urlsafe(9)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_last_cleanup = 0.0


def cleanup_old():
    """Löscht PDFs älter als RETENTION_DAYS (DSGVO). Läuft höchstens 1x pro Stunde."""
    global _last_cleanup
    if time.time() - _last_cleanup < 3600:
        return
    _last_cleanup = time.time()
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    rows = db().execute("SELECT id, filename FROM submissions WHERE created_at < ?", (cutoff,)).fetchall()
    for r in rows:
        (PDF_DIR / r["filename"]).unlink(missing_ok=True)
    db().execute("DELETE FROM submissions WHERE created_at < ?", (cutoff,))
    db().commit()


# ---------------------------------------------------------------- Hilfsfunktionen

_rate = defaultdict(list)


def rate_limited(key: str, limit: int, window: int = 3600) -> bool:
    t = time.time()
    _rate[key] = [x for x in _rate[key] if t - x < window]
    if len(_rate[key]) >= limit:
        return True
    _rate[key].append(t)
    return False


def get_object_by_token(token: str):
    obj = db().execute("SELECT * FROM objects WHERE token = ? AND active = 1", (token,)).fetchone()
    if obj is None:
        abort(404)
    return obj


def slug(s: str) -> str:
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = s.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:40] or "Objekt"


def public_base() -> str:
    return PUBLIC_URL or request.host_url.rstrip("/")


def send_mail(obj, doctype_label: str, pdf_path: Path, pages: int, note: str, created: datetime) -> str:
    to = (obj["email"] or DEFAULT_EMAIL).strip()
    if not SMTP_HOST or not to:
        return "kein SMTP"
    msg = EmailMessage()
    msg["Subject"] = f"[Objekt {obj['number']} - {obj['name']}] {doctype_label} - {created:%d.%m.%Y}"
    msg["From"] = SMTP_FROM
    msg["To"] = to
    body = [
        f"Objekt:    {obj['number']} – {obj['name']}",
        f"Adresse:   {obj['address'] or '-'}",
        f"Dokument:  {doctype_label}",
        f"Seiten:    {pages}",
        f"Eingang:   {created:%d.%m.%Y %H:%M} Uhr",
    ]
    if note:
        body += ["", "Notiz vom Mitarbeiter:", note]
    body += ["", f"– Objekt-Scanner {FIRMA}"]
    msg.set_content("\n".join(body))
    msg.add_attachment(pdf_path.read_bytes(), maintype="application", subtype="pdf", filename=pdf_path.name)
    try:
        if SMTP_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
            server.starttls()
        with server:
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return "gesendet"
    except Exception as e:  # noqa: BLE001
        app.logger.error("Mailversand fehlgeschlagen: %s", e)
        return "fehler"


def qr_svg(url: str) -> str:
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    svg = img.to_string(encoding="unicode")
    return re.sub(r"<\?xml[^>]*\?>", "", svg)


# ---------------------------------------------------------------- Mitarbeiter-Seite (ohne Login)

@app.route("/o/<token>")
def objekt_page(token):
    obj = get_object_by_token(token)
    return render_template("objekt.html", obj=obj, token=token, doc_types=DOC_TYPES, firma=FIRMA,
                           max_pages=MAX_PAGES)


@app.route("/o/<token>/scan", methods=["POST"])
def api_scan(token):
    """Vorschau: ein Foto -> Scan-Bild zurück (Base64-JPEG)."""
    get_object_by_token(token)
    if rate_limited(f"scan:{token}", 400):
        return jsonify(error="rate"), 429
    f = request.files.get("image")
    if not f:
        return jsonify(error="no image"), 400
    try:
        r = scanner.scan(f.read(), parse_corners(request.form.get("corners")))
    except Exception:  # noqa: BLE001
        return jsonify(error="bad image"), 400
    return jsonify(image="data:image/jpeg;base64," + base64.b64encode(r["jpeg"]).decode(),
                   found=r["found"], corners=r["corners"], blurry=r["blurry"], sharp=r["sharp"])


def parse_corners(raw):
    """4 relative Eckpunkte vom Mitarbeiter (JSON) prüfen, sonst None."""
    if not raw:
        return None
    try:
        pts = json.loads(raw)
        if len(pts) == 4 and all(len(p) == 2 and all(0 <= float(v) <= 1 for v in p) for p in pts):
            return [[float(x), float(y)] for x, y in pts]
    except (ValueError, TypeError):
        pass
    return None


@app.route("/o/<token>/submit", methods=["POST"])
def api_submit(token):
    obj = get_object_by_token(token)
    if rate_limited(f"submit:{token}", 60):
        return jsonify(error="rate"), 429
    doctype = request.form.get("doctype", "")
    if doctype not in DOC_TYPES:
        return jsonify(error="doctype"), 400
    files = request.files.getlist("pages")
    if not files or len(files) > MAX_PAGES:
        return jsonify(error="pages"), 400
    flags = request.form.getlist("processed")
    corners = request.form.getlist("corners")
    note = (request.form.get("note") or "").strip()[:1000]

    pages = []
    try:
        for i, f in enumerate(files):
            data = f.read()
            already = i < len(flags) and flags[i] == "1"
            if already:
                pages.append(data)
            else:
                c = parse_corners(corners[i]) if i < len(corners) else None
                pages.append(scanner.scan(data, c)["jpeg"])
        pdf = scanner.to_pdf(pages)
    except Exception:  # noqa: BLE001
        return jsonify(error="bad image"), 400

    created = datetime.now()
    rel = Path(f"{created:%Y}") / f"{created:%m}"
    (PDF_DIR / rel).mkdir(parents=True, exist_ok=True)
    fname = f"{created:%Y-%m-%d_%H%M%S}_{slug(obj['number'])}_{slug(obj['name'])}_{slug(DOC_TYPES[doctype])}.pdf"
    path = PDF_DIR / rel / fname
    path.write_bytes(pdf)

    cur = db().execute(
        "INSERT INTO submissions (object_id, doctype, pages, note, filename, created_at) VALUES (?,?,?,?,?,?)",
        (obj["id"], doctype, len(pages), note, str(rel / fname), created.strftime("%Y-%m-%d %H:%M:%S")))
    db().commit()
    status = send_mail(obj, DOC_TYPES[doctype], path, len(pages), note, created)
    db().execute("UPDATE submissions SET email_status = ? WHERE id = ?", (status, cur.lastrowid))
    db().commit()
    return jsonify(ok=True)


@app.route("/impressum")
def impressum():
    return render_template("rechtliches.html", seite="impressum", firma=FIRMA, r=RECHT)


@app.route("/datenschutz")
def datenschutz():
    return render_template("rechtliches.html", seite="datenschutz", firma=FIRMA, r=RECHT,
                           retention=RETENTION_DAYS)


@app.route("/sw.js")
def service_worker():
    resp = send_file(BASE_DIR / "static" / "sw.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/manifest/<token>.json")
def manifest(token):
    obj = get_object_by_token(token)
    return jsonify({
        "name": f"Scanner – {obj['name']}",
        "short_name": f"Scan {obj['number']}",
        "start_url": f"/o/{token}",
        "scope": f"/o/{token}",
        "display": "standalone",
        "background_color": "#F4F6F8",
        "theme_color": "#0E5A8A",
        "icons": [{"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
    })


# ---------------------------------------------------------------- Admin

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("login", next=request.path))
        return fn(*a, **kw)
    return wrapper


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if rate_limited(f"login:{request.remote_addr}", 10, 900):
            flash("Zu viele Versuche. Bitte 15 Minuten warten.")
        elif ADMIN_PASSWORD and secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session.permanent = True
            session["admin"] = True
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/admin") else url_for("dashboard"))
        else:
            flash("Falsches Passwort." if ADMIN_PASSWORD else "ADMIN_PASSWORD ist nicht gesetzt (.env).")
    return render_template("login.html", firma=FIRMA)


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@admin_required
def dashboard():
    cleanup_old()
    month = request.args.get("month") or datetime.now().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        month = datetime.now().strftime("%Y-%m")
    objects = db().execute("SELECT * FROM objects ORDER BY active DESC, number").fetchall()
    counts = defaultdict(lambda: defaultdict(int))
    for r in db().execute(
            "SELECT object_id, doctype, COUNT(*) c FROM submissions WHERE substr(created_at,1,7)=? "
            "GROUP BY object_id, doctype", (month,)):
        counts[r["object_id"]][r["doctype"]] = r["c"]
    recent = db().execute(
        "SELECT s.*, o.number, o.name FROM submissions s JOIN objects o ON o.id = s.object_id "
        "ORDER BY s.created_at DESC LIMIT 30").fetchall()
    y, m = map(int, month.split("-"))
    prev_m = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
    next_m = f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"
    return render_template("admin.html", firma=FIRMA, objects=objects, counts=counts, doc_types=DOC_TYPES,
                           recent=recent, month=month, prev_m=prev_m, next_m=next_m,
                           smtp_ok=bool(SMTP_HOST), default_email=DEFAULT_EMAIL,
                           recht_fehlt=RECHT_FEHLT)


@app.route("/admin/objekt/neu", methods=["POST"])
@admin_required
def objekt_neu():
    number = request.form.get("number", "").strip()
    name = request.form.get("name", "").strip()
    if not number or not name:
        flash("Objektnummer und Name sind Pflicht.")
        return redirect(url_for("dashboard"))
    db().execute("INSERT INTO objects (number, name, address, email, token, created_at) VALUES (?,?,?,?,?,?)",
                 (number, name, request.form.get("address", "").strip(), request.form.get("email", "").strip(),
                  new_token(), now_str()))
    db().commit()
    flash(f"Objekt {number} – {name} angelegt.")
    return redirect(url_for("dashboard"))


@app.route("/admin/objekt/<int:oid>", methods=["GET", "POST"])
@admin_required
def objekt_edit(oid):
    obj = db().execute("SELECT * FROM objects WHERE id = ?", (oid,)).fetchone() or abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save":
            db().execute("UPDATE objects SET number=?, name=?, address=?, email=?, active=? WHERE id=?",
                         (request.form.get("number", "").strip() or obj["number"],
                          request.form.get("name", "").strip() or obj["name"],
                          request.form.get("address", "").strip(), request.form.get("email", "").strip(),
                          1 if request.form.get("active") else 0, oid))
            flash("Gespeichert.")
        elif action == "newtoken":
            db().execute("UPDATE objects SET token=? WHERE id=?", (new_token(), oid))
            flash("Neuer QR-Code erstellt. Der alte funktioniert nicht mehr – bitte neu ausdrucken.")
        elif action == "delete":
            for r in db().execute("SELECT filename FROM submissions WHERE object_id=?", (oid,)):
                (PDF_DIR / r["filename"]).unlink(missing_ok=True)
            db().execute("DELETE FROM objects WHERE id=?", (oid,))
            db().commit()
            flash("Objekt gelöscht.")
            return redirect(url_for("dashboard"))
        db().commit()
        return redirect(url_for("objekt_edit", oid=oid))
    subs = db().execute("SELECT * FROM submissions WHERE object_id=? ORDER BY created_at DESC LIMIT 200",
                        (oid,)).fetchall()
    link = f"{public_base()}/o/{obj['token']}"
    return render_template("objekt_edit.html", firma=FIRMA, obj=obj, subs=subs, doc_types=DOC_TYPES,
                           link=link, qr=qr_svg(link))


@app.route("/admin/objekt/<int:oid>/plakat")
@admin_required
def objekt_plakat(oid):
    obj = db().execute("SELECT * FROM objects WHERE id = ?", (oid,)).fetchone() or abort(404)
    link = f"{public_base()}/o/{obj['token']}"
    return render_template("plakat.html", firma=FIRMA, obj=obj, qr=qr_svg(link), link=link)


@app.route("/admin/pdf/<int:sid>")
@admin_required
def pdf_download(sid):
    s = db().execute("SELECT filename FROM submissions WHERE id=?", (sid,)).fetchone() or abort(404)
    path = (PDF_DIR / s["filename"]).resolve()
    if PDF_DIR.resolve() not in path.parents or not path.exists():
        abort(404)
    return send_file(path, mimetype="application/pdf", download_name=path.name)


@app.route("/admin/pdf/<int:sid>/resend", methods=["POST"])
@admin_required
def pdf_resend(sid):
    s = db().execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone() or abort(404)
    obj = db().execute("SELECT * FROM objects WHERE id=?", (s["object_id"],)).fetchone()
    created = datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M:%S")
    status = send_mail(obj, DOC_TYPES.get(s["doctype"], s["doctype"]), PDF_DIR / s["filename"], s["pages"],
                       s["note"], created)
    db().execute("UPDATE submissions SET email_status=? WHERE id=?", (status, sid))
    db().commit()
    flash(f"E-Mail: {status}")
    return redirect(request.referrer or url_for("dashboard"))


@app.errorhandler(404)
def not_found(_e):
    return Response(render_template("404.html", firma=FIRMA), 404)


@app.errorhandler(413)
def too_large(_e):
    return jsonify(error="too large"), 413


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=os.environ.get("DEBUG") == "1")
