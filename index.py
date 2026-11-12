#!/usr/bin/env python3
"""Resmi Gazete sağlık tarayıcısı.

Kullanım:
  python scraper.py                  # son 2 gün (varsayılan)
  python scraper.py --days 30        # son 30 gün
  python scraper.py --from 2026-01-01 --to 2026-11-12   # geçmişe dönük doldurma

Mevcut saglik_arsiv_2026.json dosyasını EZMEZ; yeni kayıtları birleştirir
(aynı başlık + tarih + kategori tekrar eklenmez). Elle eklediğiniz kayıtlar korunur.
"""
import argparse
import hashlib
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

OUTPUT_FILE = "saglik_arsiv_2026.json"
BASE = "https://www.resmigazete.gov.tr"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
MAX_BODY_FETCH_PER_DAY = 25  # genel başlıklı maddelerde içerik kontrolü üst sınırı

BADGES = {
    "mevzuat": ("Mevzuat Yeniliği", "bg-blue-50 text-blue-700 border-blue-200"),
    "atama": ("Atama Kararı", "bg-amber-50 text-amber-700 border-amber-200"),
    "ilan": ("İlan / Sınav", "bg-emerald-50 text-emerald-700 border-emerald-200"),
}

# Başlıkta geçmesi yeterli olan, sağlığa özgü ifadeler
STRONG_HEALTH = [
    "sağlık bakanlığı", "sağlık müdürlü", "sağlık enstitü", "tüseb", "titck",
    "türkiye ilaç ve tıbbi cihaz", "tıbbi", "ilaç", "eczac", "eczane",
    "hastane", "hekim", "tabip", "diş hekim", "tıp ", "tıpta", "klinik",
    "sağlık hizmet", "sağlık personel", "sağlık meslek", "halk sağlığı",
    "kanser", "aşı", "hasta ", "hasta hak", "ambulans", "acil sağlık",
    "uzmanlık", "tus ", "kozmetik", "gıda takviyesi", "tütün", "bağımlılık",
    "sosyal güvenlik kurumu sağlık", "sağlık uygulama tebliği", "sut ",
]
# Başlığı genel olan (içeriğine bakılması gereken) ifadeler
GENERIC_TITLE = [
    "atama", "görevden", "kararları", "kararı", "ilan", "yönetmelik",
    "tebliğ", "kanun", "kararname", "duyuru",
]
# Gövdede aranacak kurum ifadeleri (genel başlıklı maddeler için)
BODY_HEALTH = [
    "sağlık bakanlığı", "sağlık bakan yardımcı", "il sağlık müdür",
    "türkiye ilaç ve tıbbi cihaz", "titck", "tüseb", "başhekim",
    "sağlık bilimleri üniversitesi", "halk sağlığı genel müdür",
]
ATAMA_WORDS = ["atama", "görevden", "görevlendir", "görev yeri", "vekâlet"]
ILAN_WORDS = ["ilan", "ihale", "alım", "alımı", "sınav", "duyuru", "mülakat",
              "yerleştirme", "tus", "personel"]

SECTION_NAMES = {
    "YÜRÜTME VE İDARE BÖLÜMÜ": "yurutme",
    "YARGI BÖLÜMÜ": "yargi",
    "İLAN BÖLÜMÜ": "ilan",
    "İLANLAR BÖLÜMÜ": "ilan",
    "İLANLAR": "ilan",
}


def tr_lower(s: str) -> str:
    """Türkçe'ye uygun küçük harfe çevirme (İ→i, I→ı)."""
    return (s or "").replace("İ", "i").replace("I", "ı").lower()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", tr_lower(s)).strip()


def tr_upper(s: str) -> str:
    return (s or "").replace("i", "İ").replace("ı", "I").upper()


def stable_id(*parts: str) -> int:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:12], 16)  # JS Number.MAX_SAFE_INTEGER içinde kalır


def get(url: str, retries: int = 3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            return r
        except requests.RequestException as e:
            print(f"   ağ hatası ({i + 1}/{retries}): {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    return None


def decode(r) -> str:
    # Resmi Gazete UTF-8 yayınlar; yanlış tahmini önlemek için zorla.
    r.encoding = "utf-8"
    return r.text


def fetch_body(url: str) -> str:
    r = get(url, retries=2)
    if r is None or r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
        return ""
    soup = BeautifulSoup(decode(r), "html.parser")
    return norm(soup.get_text(" "))


def classify(title_n: str, section: str) -> str:
    if section == "ilan":
        return "ilan"
    if any(w in title_n for w in ATAMA_WORDS):
        return "atama"
    if any(w in title_n for w in ILAN_WORDS) and not any(
        w in title_n for w in ("yönetmelik", "tebliğ", "kanun")
    ):
        return "ilan"
    return "mevzuat"


def guess_institution(text_n: str) -> str:
    if "tüseb" in text_n or "sağlık enstitü" in text_n or "kanser enstitü" in text_n:
        return "Türkiye Sağlık Enstitüleri Başkanlığı (TÜSEB)"
    if ("titck" in text_n or "ilaç ve tıbbi cihaz" in text_n or "tıbbi ürün" in text_n
            or "imalathane" in text_n or "ilaç" in text_n):
        return "Türkiye İlaç ve Tıbbi Cihaz Kurumu (TİTCK)"
    if "sağlık bakanlığı" in text_n or "sağlık müdür" in text_n:
        return "T.C. Sağlık Bakanlığı"
    return "T.C. Resmi Gazete"


def iter_entries(soup: BeautifulSoup, page_url: str):
    """Belge sırasıyla (bölüm, başlık, url) üretir. Bölüm başlıklarını izler."""
    section = "yurutme"
    seen = set()
    for el in soup.find_all(True):
        if el.name == "a" and el.get("href"):
            title = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            href = el["href"].strip()
            if not title or len(title) < 8 or href.startswith(("#", "javascript:", "mailto:")):
                continue
            url = urljoin(page_url, href)
            if (title, url) in seen:
                continue
            seen.add((title, url))
            yield section, title, url
        elif el.name in ("div", "span", "h1", "h2", "h3", "h4", "p", "td", "li") and not el.find("a"):
            txt = tr_upper(re.sub(r"\s+", " ", el.get_text(" ", strip=True)))
            if txt in SECTION_NAMES:
                section = SECTION_NAMES[txt]


def scrape_day(d: date):
    ds = d.strftime("%Y%m%d")
    url = f"{BASE}/eskiler/{d:%Y}/{d:%m}/{ds}.htm"
    print(f"Taranıyor: {url}")
    r = get(url)
    if r is None:
        print("   -> erişilemedi")
        return []
    if r.status_code != 200:
        print(f"   -> yayın yok/erişilemiyor (HTTP {r.status_code})")
        return []

    soup = BeautifulSoup(decode(r), "html.parser")
    items, body_fetches = [], 0
    for section, title, link in iter_entries(soup, url):
        t_n = norm(title)
        strong = any(k in t_n for k in STRONG_HEALTH)
        generic = any(k in t_n for k in GENERIC_TITLE)
        body_n = ""
        if not strong and generic and body_fetches < MAX_BODY_FETCH_PER_DAY:
            # Başlık genel ("... Atama Kararları") → içeriğinde sağlık kurumu geçiyor mu?
            body_n = fetch_body(link)
            body_fetches += 1
            time.sleep(0.4)
            if not any(k in body_n for k in BODY_HEALTH):
                continue
        elif not strong:
            continue

        cat = classify(t_n, section)
        label, badge = BADGES[cat]
        items.append({
            "id": stable_id(d.isoformat(), cat, t_n),
            "category": cat,
            "categoryLabel": label,
            "badgeColor": badge,
            "title": title,
            "institution": guess_institution(t_n + " " + body_n[:4000]),
            "summary": "Resmi Gazete'den otomatik taranmıştır. Ayrıntı için orijinal metne bakınız.",
            "date": d.isoformat(),
            "url": link,
            "source": "auto",
        })
    print(f"   -> {len(items)} sağlık kaydı")
    return items


def load_existing(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def merge(existing, new):
    """Aynı (tarih, kategori, başlık) tekrar eklenmez; mevcut kayıtlar korunur."""
    def key(it):
        return (it.get("date"), it.get("category"), norm(it.get("title", "")))

    have = {key(it) for it in existing}
    added = 0
    for it in new:
        if key(it) not in have:
            existing.append(it)
            have.add(key(it))
            added += 1
    existing.sort(key=lambda x: (x.get("date", ""), x.get("id", 0)), reverse=True)
    return existing, added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2, help="bugünden geriye kaç gün")
    ap.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", help="YYYY-MM-DD (varsayılan bugün)")
    ap.add_argument("--out", default=OUTPUT_FILE)
    args = ap.parse_args()

    # GitHub runner UTC çalışır; Türkiye tarihi için +3 saat
    today = (datetime.utcnow() + timedelta(hours=3)).date()
    end = date.fromisoformat(args.date_to) if args.date_to else today
    start = (date.fromisoformat(args.date_from) if args.date_from
             else end - timedelta(days=max(args.days, 1) - 1))

    new, d = [], start
    while d <= end:
        new.extend(scrape_day(d))
        d += timedelta(days=1)
        time.sleep(0.5)

    merged, added = merge(load_existing(args.out), new)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"Bitti. Yeni: {added}, toplam arşiv: {len(merged)} → {args.out}")


if __name__ == "__main__":
    main()
