from datetime import datetime, timedelta
import json
from bs4 import BeautifulSoup
import requests


def scrape_resmi_gazete_tarih(target_date):
  """Belirli bir tarihteki Resmi Gazete arşivini tarar ve sağlık kararlarını ayıklar."""
  date_str = target_date.strftime("%Y%m%d")
  year = target_date.strftime("%Y")
  month = target_date.strftime("%m")

  url = f"https://www.resmigazete.gov.tr/eskiler/{year}/{month}/{date_str}.htm"
  print(f"Taranıyor: {url}")

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  try:
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
      print(f"-> {target_date.strftime('%d.%m.%Y')} tarihli gazete bulunamadı.")
      return []

    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    health_keywords = [
        "sağlık bakanlığı",
        "tüseb",
        "tİck",
        "türkiye ilaç ve tıbbi cihaz",
        "bilim kurulları",
        "yönetmelik",
        "tebliğ",
        "atama",
        "görevden",
        "eczacı",
        "ilaç",
        "tıbbi cihaz",
        "hastane",
        "kanser",
    ]

    found_items = []
    links = soup.find_all("a")

    for link in links:
      title = link.get_text(strip=True)
      href = link.get("href", "")

      if any(kw in title.lower() for kw in health_keywords):
        if not href.startswith("http"):
          href = f"https://www.resmigazete.gov.tr/eskiler/{year}/{month}/{href}"

        category = "mevzuat"
        category_label = "Mevzuat Yeniliği"
        badge_color = "bg-blue-50 text-blue-700 border-blue-200"

        if "atama" in title.lower() or "görevden" in title.lower():
          category = "atama"
          category_label = "Atama Kararı"
          badge_color = "bg-amber-50 text-amber-700 border-amber-200"
        elif "ilan" in title.lower() or "alımı" in title.lower():
          category = "ilan"
          category_label = "İlan / Sınav"
          badge_color = "bg-emerald-50 text-emerald-700 border-emerald-200"

        found_items.append({
            "id": int(datetime.now().timestamp() * 1000),
            "category": category,
            "categoryLabel": category_label,
            "badgeColor": badge_color,
            "title": title,
            "institution": "T.C. Resmi Gazete",
            "summary": "Resmi Gazete arşivinden otomatik tarandı.",
            "date": target_date.strftime("%Y-%m-%d"),
            "url": href,
        })

    return found_items

  except Exception as e:
    print(f"Hata oluştu ({date_str}): {e}")
    return []


def tarama_baslat():
  # Örnek olarak sadece bugünün veya son birkaç günün taraması
  today = datetime.now()
  start_date = today - timedelta(days=2)  # Son 2 günü tara

  tum_sonuclar = []
  aktif_tarih = start_date

  while aktif_tarih <= today:
    gunluk_sonuclar = scrape_resmi_gazete_tarih(aktif_tarih)
    if gunluk_sonuclar:
      tum_sonuclar.extend(gunluk_sonuclar)
    aktif_tarih += timedelta(days=1)

  # Mevcut JSON dosyası varsa üzerine ekle veya yenisini oluştur
  dosya_adi = "saglik_arsiv_2026.json"
  with open(dosya_adi, "w", encoding="utf-8") as f:
    json.dump(tum_sonuclar, f, ensure_ascii=False, indent=4)

  print(f"Tarama bitti. {len(tum_sonuclar)} kayıt kaydedildi.")


if __name__ == "__main__":
  tarama_baslat()