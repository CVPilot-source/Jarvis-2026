# Objekt-Scanner

Me këtë app, Mitarbeiter-ët dërgojnë **Reinigungsnachweis, Stundenzettel dhe Abnahmezettel për Sonderleistung** me telefon, **pa emër dhe pa login**. Mjafton të skanojnë QR-Code-in e objektit. Aplikacioni e bën foton si scanner (e drejton, heq hijet), e kthen në PDF dhe e dërgon me email në zyrë.

## Si funksionon

| Kush | Çfarë bën |
|---|---|
| **Mitarbeiter** | Skanon QR-Code-in në objekt → zgjedh dokumentin → bën foto (1 ose më shumë faqe) → „Senden“ |
| **App-i** | Gjen skajet e letrës, e drejton, heq hijet → PDF → email me emër të rregullt |
| **Ti (Admin)** | Shton objekte, printon Aushang me QR-Code, sheh në Monatsübersicht çfarë mungon |

**Shembull emaili:**
```
Betreff: [Objekt 0142 - Praxis Dr. Weber] Stundenzettel - 26.11.2026
Anhang:  2026-11-26_205620_0142_Praxis-Dr-Weber_Stundenzettel.pdf
```

**Funksione:**
- 7 gjuhë për Mitarbeiter-ët: DE, SQ, TR, RO, PL, AR, EN
- Funksionon edhe **pa internet**: dokumenti ruhet në telefon dhe dërgohet vetë kur kthehet lidhja
- Çdo objekt mund të ketë **adresën e vet të emailit**, p.sh. për Objektleiter të ndryshëm
- **Monatsübersicht:** tregon me ✓ ose „fehlt“ çdo objekt dhe çdo lloj dokumenti
- **Neuer QR-Code:** nëse QR-Code-i i vjetër del jashtë firmës, e bllokon me një klik
- **DSGVO:** PDF-të fshihen automatikisht pas `RETENTION_DAYS` ditësh

---

## Testim në kompjuter (5 minuta)

```bash
cd objekt-scanner
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
ADMIN_PASSWORD=test123 python3 app.py
```
Hap në browser: <http://localhost:5050/admin> me fjalëkalimin `test123`.

---

## Instalimi në serverin Hetzner

Këtu supozohet Ubuntu ose Debian me nginx. Serveri yt ekzistues (NEO) vazhdon të punojë normalisht, sepse ky app përdor portin **5050** dhe një **subdomain** të vetin.

### 1. Subdomain
Te DNS-i i domain-it tënd, krijo një rekord **A**: `scan.deine-domain.de` → IP-ja e serverit Hetzner.

### 2. Kopjo app-in në server
```bash
sudo apt update && sudo apt install -y python3-venv nginx certbot python3-certbot-nginx git
sudo useradd --system --home /opt/objekt-scanner scanner
sudo git clone <REPO-URL> /tmp/repo && sudo cp -r /tmp/repo/objekt-scanner /opt/objekt-scanner
cd /opt/objekt-scanner
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt
```

### 3. Konfigurimi (`.env`)
```bash
sudo cp .env.example .env
sudo nano .env      # plotëso firmën, fjalëkalimin, SMTP, emailin
sudo chown -R scanner:scanner /opt/objekt-scanner
sudo chmod 600 .env
```
> **SMTP:** përdor një postë të firmës, p.sh. `scanner@firma.de`. Për Microsoft 365 / Outlook duhet që administratori i IT-së të lejojë „SMTP AUTH“ për këtë postë.

### 4. Nise si shërbim
```bash
sudo cp deploy/objekt-scanner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now objekt-scanner
sudo systemctl status objekt-scanner      # duhet të shkruajë "active (running)"
```

### 5. nginx + HTTPS
```bash
sudo cp deploy/nginx-scan.conf /etc/nginx/sites-available/scan
sudo nano /etc/nginx/sites-available/scan     # vendos subdomain-in tënd
sudo ln -s /etc/nginx/sites-available/scan /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d scan.deine-domain.de
```
**Gati.** Hap `https://scan.deine-domain.de/admin`.

> HTTPS është i detyrueshëm: pa të kamera dhe funksioni offline nuk punojnë mirë në telefon.

### Përditësim
```bash
cd /tmp/repo && sudo git pull && sudo cp -r objekt-scanner/*.py objekt-scanner/templates objekt-scanner/static /opt/objekt-scanner/
sudo systemctl restart objekt-scanner
```

### Backup
Të gjitha të dhënat janë në `/opt/objekt-scanner/data/`: databaza `scanner.db` dhe PDF-të. Mjafton të ruash këtë folder. Mund të përdorësh edhe **Hetzner Backups** ose **Snapshots**.

---

## Para prezantimit në firmë: lista e kontrollit

- [ ] 2–3 objekte demo të krijuara, Aushang i printuar
- [ ] Testo me telefonin tënd: skano QR → foto → email arrin
- [ ] Trego **Monatsübersicht** („fehlt“ / ✓): kjo kursen kohë më shumë se çdo gjë tjetër
- [ ] Trego një objekt në **shqip ose turqisht** për Mitarbeiter-ët
- [ ] Trego testin offline (Flugmodus → dërgo → Flugmodus off → arrin)

## DSGVO / Datenschutz (për bisedën me shefin)

- Serveri është në **Gjermani (Hetzner Nürnberg)**. Me Hetzner duhet të ekzistojë **AVV** (bëhet online te Hetzner Robot/Console).
- Mitarbeiter-ët **nuk regjistrohen**: nuk ruhet as emër, as telefon, as IP në databazë.
- Stundenzettel-at kanë të dhëna personale, prandaj: HTTPS, fshirje automatike, akses në Admin vetëm me fjalëkalim.
- Nëse ka **Betriebsrat**, duhet informuar para nisjes, sepse bëhet fjalë për të dhëna për orët e punës.

## Struktura e kodit

```
objekt-scanner/
├── app.py            Server (Flask): objektet, upload, PDF, email, admin
├── scanner.py        Efekti scanner (OpenCV): skajet, perspektiva, hijet
├── templates/        Faqet HTML (Mitarbeiter, Admin, Aushang)
├── static/           CSS, JavaScript, Service Worker (offline)
├── deploy/           systemd + nginx për Hetzner
└── .env.example      Konfigurimi
```
