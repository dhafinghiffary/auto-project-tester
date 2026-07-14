# auto-project-tester

AI generates a pytest test suite for a repo (ZIP or public GitHub URL), runs it inside an
isolated Docker sandbox, and returns a detailed pass/fail test report. v1 supports Python
projects only.

## Setup lokal

```
python -m venv venv
venv\Scripts\Activate.ps1        # atau source venv/bin/activate di macOS/Linux
pip install -r requirements.txt
```

`.env` sudah disiapkan (di-copy dari `auto-document-generator`, pakai `GOOGLE_API_KEY` yang sama).
Kalau mau pakai key lain, edit `.env` (lihat `.env.example` untuk formatnya).

**Docker Desktop harus jalan** sebelum start server — sandbox eksekusi test butuh Docker daemon.
Image sandbox (`auto-project-tester-sandbox:latest`) di-build otomatis saat request pertama masuk
(butuh beberapa puluh detik sekali saja, setelah itu di-cache oleh Docker).

Jalankan server:
```
uvicorn app.main:app --reload
```

Buka `http://127.0.0.1:8000` di browser — ada halaman upload sederhana (ZIP atau URL GitHub).
Swagger/API docs ada di `http://127.0.0.1:8000/docs`.

## Cara paling cepat untuk coba (smoke test)

Ada `sample_repo.zip` di root project — project Python sintetis kecil (`mathkit`) dengan beberapa
fungsi dan **satu bug yang sengaja ditaruh** di fungsi `clamp()` (lihat `sample_repo/mathkit/calculator.py`).
Upload file itu lewat tab "Upload ZIP" di halaman web, atau lewat curl:

```
curl -X POST http://127.0.0.1:8000/test/zip -F "file=@sample_repo.zip"
```

Proses penuh (analisis kode → generate test dengan Gemini → jalan di sandbox Docker) biasanya
makan waktu 1-3 menit tergantung kecepatan Gemini API dan Docker. Kalau AI-generated test-nya
cukup bagus, harusnya ada minimal satu test yang FAILED terkait `clamp()` — itu tandanya
pipeline-nya benar-benar jalan end-to-end dan bukan cuma "selalu PASSED" palsu.

Untuk coba repo GitHub publik:
```
curl -X POST http://127.0.0.1:8000/test/github -H "Content-Type: application/json" \
  -d "{\"repo_url\": \"https://github.com/<owner>/<repo-python-kecil>\"}"
```
(pilih repo Python yang kecil dulu untuk percobaan pertama)

## Yang perlu kamu cek pertama kali bangun

1. `uvicorn app.main:app --reload` jalan tanpa error import.
2. Buka `http://127.0.0.1:8000`, upload `sample_repo.zip`, lihat laporan muncul dengan
   ringkasan pass/fail dan minimal satu kegagalan di `clamp` (atau baca `CLAUDE.md` bagian
   "Keterbatasan" kalau ada yang tidak sesuai ekspektasi).
3. Kalau ada error saat build image Docker pertama kali, jalankan manual untuk lihat pesan
   lengkap: `docker build -f docker/sandbox.Dockerfile -t auto-project-tester-sandbox:latest docker`
