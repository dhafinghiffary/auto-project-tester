# auto-project-tester

## Apa yang sedang dibangun

Project baru, saudara dari `auto-document-generator` (arsitektur pipeline yang sama: user
kasih repo → sistem analisis kode → LLM proses → hasil siap pakai), tapi outputnya beda:
bukan dokumen SDD/UAT, melainkan **hasil testing detail beneran** — AI menulis test code
(pytest), test itu benar-benar **dijalankan** di sandbox terisolasi, dan hasilnya (pass/fail,
error, traceback) dilaporkan ke user.

**Keputusan desain yang disengaja (2026-07-15, dipilih user sebelum tidur, lihat memory
`project-auto-project-tester` untuk detail percakapan):**
- Output = eksekusi test beneran, bukan sekadar dokumen skenario test (opsi yang lebih
  ambisius & berisiko keamanan dibanding sekadar generate dokumen, karena berarti sistem
  menjalankan kode yang belum tentu bisa dipercaya).
- Dibangun dari nol — tidak reuse kode ingestion/parser dari `auto-document-generator`
  (arsitektur mirip secara konsep, tapi implementasi independen).
- Repo lokal dulu (`C:\Kuliah\Magang\auto-project-tester`), belum di-push ke GitHub.

## Alur sistem (yang sudah diimplementasikan v1)

```
Source Input (ZIP upload / URL GitHub publik via git clone)
        ↓
Workspace (temp dir per-request, lihat app/ingestion/workspace.py)
        ↓
Code Analyzer (Python ast module — deterministik, bukan LLM baca kode mentah)
        ↓
ParsedProjectContext (per file: functions/classes/methods, signature, docstring)
        ↓
LLM Test Generator (Gemini via LangChain, with_structured_output)
        ↓
Generated pytest test files (ditulis ke <workspace>/generated_tests/)
        ↓
Sandbox Executor (Docker, container efemeral, 2 fase: install deps [network ON] →
                   disconnect network → jalankan pytest [network OFF])
        ↓
Report Generator (JSON terstruktur + Markdown human-readable)
```

**Update 2026-07-15**: sekarang berjalan sebagai job asinkron, bukan request sinkron yang
blocking. `POST /test/zip` / `/test/github` langsung return `job_id` (202) dan proses jalan di
thread terpisah (`app/services/job_store.py`); client poll `GET /test/jobs/{id}` untuk lihat
stage berjalan (`Menganalisis struktur kode...` → `Generate test dengan AI...` → `Menjalankan
test di sandbox Docker...` → `Selesai`) dan hasil akhirnya. Riwayat job tersimpan di
`job_history/` (file JSON, bukan database) lewat `GET /test/jobs`. Ini juga memperbaiki bug
awal: sebelumnya pipeline blocking dijalankan langsung di dalam `async def` route handler,
yang berarti SATU request lambat membekukan seluruh server untuk semua request lain juga
(bukan cuma request itu sendiri) — sudah diperbaiki dengan `run_in_threadpool`/`BackgroundTasks`.
Untuk repo kecil biasanya 1-3 menit tergantung Gemini API + waktu Docker install/exec.

## Kenapa Docker sandbox, bukan langsung `subprocess.run` di host

Sistem ini menjalankan kode yang datang dari user (via ZIP/GitHub URL) — tidak bisa dipercaya
begitu saja. Kalau langsung dieksekusi di host, itu = remote code execution vulnerability.
Mitigasi yang diimplementasikan di `app/services/sandbox_executor.py`:
- Container efemeral, non-root user (`runner`), `cap_drop=["ALL"]`, `security_opt=no-new-privileges`.
- Resource limits: `mem_limit=512m`, `nano_cpus` (1 CPU), `pids_limit=128`.
- **Network di-disconnect sebelum test dijalankan** — instalasi dependency (`pip install`)
  butuh network, tapi eksekusi test-nya sendiri TIDAK, jadi network diputus di antara dua fase
  itu (pakai Docker API `network.disconnect`, bukan container terpisah, supaya package yang
  sudah ke-install tetap kepakai).
- Timeout keras per fase (`timeout` command di dalam container: 90s install, 60s test run).
- Container di-`stop()` + `remove(force=True)` di blok `finally`, apa pun hasilnya.

**Ini BUKAN sandbox tingkat produksi/multi-tenant hardened** (bukan gVisor/Firecracker/microVM)
— cukup untuk prototipe single-user lokal, TIDAK cukup untuk SaaS publik yang menerima repo
dari orang asing tanpa isolasi lebih kuat. Lihat "Keterbatasan" di bawah.

## Struktur folder

```
app/
  domain/models.py     # semua Pydantic model (ParsedProjectContext, GeneratedTestFile,
                        #   ExecutionResult, TestReport, dll)
  ingestion/
    workspace.py        # temp dir per-request
    zip_ingest.py        # extract ZIP aman (guard zip-bomb, zip-slip/path traversal)
    github_ingest.py      # shallow clone repo publik (validasi URL ketat, no OAuth di v1)
    errors.py             # IngestionError
  services/
    code_analyzer.py       # parser AST Python (functions/classes/signature/docstring)
    test_generator_service.py  # LLMService setara: generate pytest test dari context
    sandbox_executor.py         # orkestrasi Docker, dua-fase, lihat penjelasan di atas
    report_service.py            # build TestReport (JSON + markdown) dari hasil eksekusi
    pipeline.py                   # rangkai semua tahap jadi run_pipeline(..., on_stage=callback)
    job_store.py                   # TestJob in-memory dict + persist ke job_history/*.json
    errors.py                      # SandboxError
  api/
    routes_test.py    # POST /test/zip, POST /test/github (return job_id, 202),
                       #   GET /test/jobs/{id}, GET /test/jobs (history)
    schemas.py          # request schema (GithubTestRequest)
  core/config.py     # load .env (GOOGLE_API_KEY)
  main.py            # FastAPI app, serve static/index.html di "/"
static/index.html   # UI upload sederhana (tab ZIP / URL GitHub), polling job status + riwayat
docker/sandbox.Dockerfile   # image sandbox: python:3.11-slim, user non-root, venv, pytest
sample_repo/         # project Python sintetis kecil dengan 1 bug sengaja (buat smoke test)
sample_repo.zip       # sample_repo di-zip, siap upload langsung
job_history/           # (gitignored) riwayat job sebagai file JSON, dibaca job_store.py
```

## Tech stack

Python + FastAPI, `docker` SDK (orkestrasi sandbox), LangChain + Google Gemini (`gemini-2.5-flash`,
`with_structured_output`, pola sama seperti `LLMService` di `auto-document-generator`), Python
`ast` module untuk parsing (bukan Tree-sitter — cukup untuk Python-only v1, generic multi-bahasa
bisa nyusul kalau perlu), pytest + `pytest-json-report` (dijalankan di dalam container, bukan di host).

## Kontrak internal antar-tahap (solo project, tapi tetap didokumentasikan biar jelas)

**ParsedProjectContext** (Code Analyzer → LLM Test Generator): per file ada `module_name`
(dotted path relatif ke root, dipakai LLM buat nulis `import`), `functions[]`, `classes[].methods[]`
masing-masing dengan `parameters[]` (name/annotation/default), `return_annotation`, `docstring`.

**TestGenerationResult** (LLM Test Generator → Sandbox Executor): `files[]` berisi `filename`
(pola wajib `test_*.py`), `target_module`, `content` (kode Python lengkap). Nama file dan target
module divalidasi/dibersihkan di `test_generator_service.py` sebelum ditulis ke disk (anti path
traversal dari output LLM, anti nama file bentrok).

**ExecutionResult** (Sandbox Executor → Report Generator): `install_success`, `install_log`,
`timed_out`, `summary` (total/passed/failed/errors/skipped/duration), `tests[]` (node_id/outcome/
duration/message). Diparse dari `pytest-json-report` JSON output.

## Setup lokal

Lihat `README.md` — ringkasnya: `venv` + `pip install -r requirements.txt`, `.env` sudah ada
(`GOOGLE_API_KEY` di-copy dari `auto-document-generator`), Docker Desktop harus jalan, lalu
`uvicorn app.main:app --reload`. Ada `sample_repo.zip` buat smoke test langsung tanpa perlu cari
repo dulu.

## Keterbatasan yang diketahui (belum dikerjakan, bukan bug)

- **Python saja** — parser (`ast` module) tidak paham JS/TS/bahasa lain. Repo non-Python akan
  menghasilkan `ParsedProjectContext` kosong (tidak ada function/class terdeteksi) dan generated
  test kosong.
- **Tidak ada OAuth/PAT untuk repo privat** — hanya clone repo GitHub publik tanpa autentikasi.
- **Sandbox Docker belum hardened untuk multi-tenant publik** (lihat penjelasan bagian atas) —
  cukup untuk pemakaian lokal/personal, JANGAN di-deploy sebagai SaaS publik tanpa isolasi lebih
  kuat (gVisor, Firecracker/microVM, atau layanan sandbox managed) plus rate limiting & auth.
- **~~Sinkron, bukan job queue~~ — sudah diperbaiki 2026-07-15**: `POST /test/zip` dan
  `/test/github` sekarang langsung return `job_id` (202) dan jalan di background thread
  (`BackgroundTasks` + threadpool), bukan blocking event loop. Progress per-stage dan riwayat job
  bisa dicek lewat `GET /test/jobs/{id}` dan `GET /test/jobs` (disimpan sebagai file JSON di
  `job_history/`, bukan database — cukup untuk skala saat ini). Lihat `app/services/job_store.py`.
- **Kuota gratis Gemini API cuma 20 request/hari** (free tier `gemini-2.5-flash`) — kepakai habis
  cuma dari testing semalam + hari ini. Kalau kena `RESOURCE_EXHAUSTED (429)`, tunggu reset kuota
  harian (sekitar tengah malam Pacific Time) atau ganti `GOOGLE_API_KEY` di `.env` ke key lain/plan
  berbayar. Ini WAJIB diperhitungkan sebelum ada rencana multi-user beneran — 20 request/hari tidak
  akan cukup untuk lebih dari segelintir test run per hari.
- **Timeout Gemini call 150s, 1x retry** (`test_generator_service.py`) — sebelumnya tanpa timeout
  sama sekali sehingga request yang lambat bisa menggantung selamanya tanpa pernah gagal ataupun
  selesai; ini penyebab paling mungkin dari laporan "macet lama tanpa hasil" di awal pemakaian.
- **Workspace tidak di-cleanup otomatis** — tiap request bikin folder baru di `workspaces/`
  (di-gitignore), tidak dihapus setelah selesai, supaya bisa diinspeksi manual untuk debugging.
  Perlu dibersihkan manual atau ditambah cleanup job kalau dipakai lama.
- **Belum ada unit test untuk kode `auto-project-tester` sendiri** (ironis, tapi memang belum
  sempat — prioritas semalam adalah pipeline utamanya jalan dulu).
- **`analyze_project` membatasi ke 40 file pertama** dan **LLM prompt dibatasi ke 15 file** —
  supaya prompt tidak meledak untuk repo besar. Repo besar akan dites parsial saja.
- **Belum dites ke variasi repo Python yang luas** — baru divalidasi manual terhadap `sample_repo`
  sintetis. Perlu dicoba ke beberapa repo publik nyata untuk lihat seberapa bagus kualitas test
  yang di-generate LLM dan seberapa sering `pip install` gagal karena dependency yang aneh-aneh.
- **`generated_tests/` yang ditulis LLM tidak divalidasi syntax-nya sebelum dijalankan** — kalau
  LLM menghasilkan Python yang tidak valid, pytest akan collection-error dan itu akan muncul di
  laporan sebagai error, bukan dicegah lebih awal.
