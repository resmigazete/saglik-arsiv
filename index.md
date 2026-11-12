# Son adımlar (GitHub deposu: saglik-arsiv)

1. Depoya şu dosyaları yükleyin / üzerine yazın (Add file → Upload files):
   scraper.py, requirements.txt, index.html
   ve .github/workflows/run_scraper.yml (Add file → Create new file; yol: .github/workflows/run_scraper.yml)
2. index.html içinde GITHUB_USER değerine GitHub kullanıcı adınızı yazın.
3. Settings → Pages → Source: "Deploy from a branch", Branch: main / (root) → Save.
   Uygulama adresiniz: https://KULLANICI_ADI.github.io/saglik-arsiv/
   Telefonda açıp "Ana ekrana ekle" yapın.
4. Actions → "Resmi Gazete Saglik Scraper" → Run workflow → days = 320
   (yılbaşından bugüne tüm sağlık kayıtlarını doldurur). Sonraki günler otomatik gelir.
