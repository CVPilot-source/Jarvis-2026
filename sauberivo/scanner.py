"""Bildverarbeitung: macht aus einem Handyfoto einen sauberen "Scan".

1. EXIF-Drehung korrigieren
2. Blattkanten finden und Perspektive geraderichten
3. Schatten entfernen, Kontrast erhöhen (Graustufen, Unterschriften bleiben lesbar)
"""
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 2200  # Pixel – reicht für A4 in ~190 dpi


def _load(image_bytes: bytes) -> np.ndarray:
    pil = Image.open(BytesIO(image_bytes))
    pil = ImageOps.exif_transpose(pil).convert("RGB")
    pil.thumbnail((MAX_SIDE, MAX_SIDE))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # oben links
    rect[2] = pts[np.argmax(s)]  # unten rechts
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]  # oben rechts
    rect[3] = pts[np.argmax(d)]  # unten links
    return rect


def _find_page(img: np.ndarray):
    """Sucht das größte Viereck (= das Blatt). Gibt 4 Punkte oder None zurück."""
    h, w = img.shape[:2]
    scale = 600.0 / max(h, w)
    small = cv2.resize(img, (int(w * scale), int(h * scale)))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    min_area = 0.20 * small.shape[0] * small.shape[1]

    for lo, hi in ((30, 120), (50, 200), (10, 60)):
        edges = cv2.Canny(gray, lo, hi)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
            if cv2.contourArea(c) < min_area:
                break
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                return approx.reshape(4, 2).astype("float32") / scale
    return None


def _warp(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    rect = _order_points(pts)
    tl, tr, br, bl = rect
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    m = cv2.getPerspectiveTransform(rect, dst)
    out = cv2.warpPerspective(img, m, (width, height))
    # schmalen Rand abschneiden (Reste vom Tisch an der Blattkante)
    dx, dy = max(2, width // 100), max(2, height // 100)
    return out[dy:height - dy, dx:width - dx]


def _enhance(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Hintergrund (Papier + Schatten) schätzen und herausrechnen
    bg = cv2.dilate(gray, np.ones((7, 7), np.uint8))
    bg = cv2.medianBlur(bg, 31)
    diff = 255 - cv2.absdiff(gray, bg)
    norm = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
    # Kontrastkurve: Papier richtig weiß, Schrift kräftig
    lut = np.array([min(255, max(0, int((i - 60) * 255 / 170))) for i in range(256)], dtype=np.uint8)
    return cv2.LUT(norm, lut)


def sharpness(img: np.ndarray) -> float:
    """Schärfe-Wert (Varianz des Laplace-Filters) auf einheitlicher Größe."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    scale = 1000.0 / max(gray.shape[:2])
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


BLUR_LIMIT = 60.0  # darunter gilt das Foto als unscharf


def scan(image_bytes: bytes, corners=None) -> dict:
    """Foto -> Scan.

    corners: optional 4 Punkte [[x,y],...] relativ (0..1) – vom Mitarbeiter angepasst.
    Rückgabe: jpeg, found (Blatt erkannt), corners (relativ), sharp (Schärfe), blurry
    """
    img = _load(image_bytes)
    h, w = img.shape[:2]
    if corners:
        pts = np.array(corners, dtype="float32").reshape(4, 2) * np.array([w, h], dtype="float32")
        found = True
    else:
        pts = _find_page(img)
        found = pts is not None
    if pts is not None:
        pts = _order_points(pts)
        page = _warp(img, pts)
        rel = [[round(float(x), 4), round(float(y), 4)] for x, y in pts / np.array([w, h], dtype="float32")]
    else:
        page = img
        rel = [[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]]
    sharp = sharpness(page)
    out = _enhance(page)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return {"jpeg": buf.tobytes(), "found": found, "corners": rel, "sharp": round(sharp, 1),
            "blurry": sharp < BLUR_LIMIT}


def to_pdf(jpeg_pages: list[bytes]) -> bytes:
    """Mehrere gescannte Seiten -> ein PDF (Seitengröße ≈ A4)."""
    pages = [Image.open(BytesIO(b)).convert("L") for b in jpeg_pages]
    out = BytesIO()
    res = max(pages[0].size) / 11.69  # lange Seite = A4-Höhe in Zoll
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=res)
    return out.getvalue()
