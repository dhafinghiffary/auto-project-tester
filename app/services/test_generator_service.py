from __future__ import annotations

import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.domain.models import GeneratedTestFile, ParsedProjectContext, TestGenerationResult

MAX_FILES_FOR_PROMPT = 15

SYSTEM_PROMPT = """
Anda adalah seorang QA Automation Engineer senior yang menulis pytest test suite untuk
sebuah project Python berdasarkan metadata struktur kode (hasil parsing AST, BUKAN kode mentah).

ATURAN WAJIB SUPAYA TEST BISA DIJALANKAN:
1. Test akan dijalankan dengan `python -m pytest` dari root project, jadi root project ada di sys.path.
   Import module persis dari field `module_name` yang diberikan, contoh: jika module_name adalah
   "mathkit.calculator", tulis `from mathkit.calculator import nama_fungsi` atau `import mathkit.calculator`.
2. HANYA gunakan nama fungsi/class/method yang benar-benar ada di metadata yang diberikan. DILARANG
   mengarang nama fungsi/parameter yang tidak ada di metadata (no hallucination).
3. Kalau signature fungsi tidak punya cukup informasi untuk menebak nilai input yang valid (misal
   butuh koneksi database/network/file eksternal), JANGAN dipaksa dites dengan asumsi liar -- tandai
   dengan `@pytest.mark.skip(reason="...")` dan jelaskan alasannya singkat.
4. Fokus ke behavior yang bisa diuji murni dari signature + docstring: normal case, edge case
   (nilai kosong/None/negatif/batas), dan error case (exception yang diharapkan bila relevan).
5. Setiap file test HARUS valid Python syntax, importable, dan tidak butuh dependency di luar yang
   sudah ada di requirements project atau pytest itu sendiri (jangan import library yang tidak jelas
   tersedia).
6. Jangan bungkus kode dengan markdown fence (```). Tulis isi file .py murni saja.
7. Nama file test HARUS berpola `test_<sesuatu>.py`.
8. Batasi ke test yang benar-benar bernilai -- tidak perlu test getter/setter trivial yang tidak
   punya logika sama sekali.
"""

HUMAN_PROMPT = """
Berikut metadata project (hasil parsing AST, per file: functions/classes/methods dengan signature
dan docstring-nya):

{project_context}

Generate pytest test file(s) untuk sebanyak mungkin fungsi/method yang bernilai untuk diuji.
"""


class _LLMGeneratedTestFile(BaseModel):
    filename: str = Field(description="Nama file test, pola test_<sesuatu>.py")
    target_module: str = Field(description="module_name yang diuji oleh file ini, sesuai metadata")
    content: str = Field(description="Isi lengkap file .py, valid Python, tanpa markdown fence")


class _LLMTestGenerationResult(BaseModel):
    files: list[_LLMGeneratedTestFile] = Field(description="Daftar file test yang dihasilkan")
    model_notes: str | None = Field(
        default=None, description="Catatan singkat: fungsi apa yang di-skip dan kenapa, kalau ada"
    )


_FENCE_RE = re.compile(r"^```(?:python)?\n|\n```$", re.MULTILINE)


def _strip_fences(content: str) -> str:
    return _FENCE_RE.sub("", content).strip() + "\n"


def _safe_test_filename(name: str, fallback_index: int) -> str:
    name = name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
    if not re.match(r"^[\w.-]+\.py$", name) or not (name.startswith("test_") or name.endswith("_test.py")):
        name = f"test_generated_{fallback_index}.py"
    return name


class TestGeneratorService:
    def __init__(self) -> None:
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.structured_llm = self.llm.with_structured_output(_LLMTestGenerationResult)

    def generate_tests(self, context: ParsedProjectContext) -> TestGenerationResult:
        testable_files = [
            f for f in context.files
            if not f.parse_error and (f.functions or f.classes)
        ][:MAX_FILES_FOR_PROMPT]

        if not testable_files:
            return TestGenerationResult(files=[], model_notes="Tidak ada fungsi/class yang bisa dites di repo ini.")

        project_context = {
            "project_name": context.project_name,
            "files": [f.model_dump(exclude={"parse_error"}) for f in testable_files],
        }

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ])
        chain = prompt | self.structured_llm

        result: _LLMTestGenerationResult = chain.invoke({
            "project_context": json.dumps(project_context, indent=2),
        })

        seen_names: set[str] = set()
        files: list[GeneratedTestFile] = []
        for i, f in enumerate(result.files):
            name = _safe_test_filename(f.filename, i)
            while name in seen_names:
                name = f"{name[:-3]}_{i}.py"
            seen_names.add(name)
            files.append(GeneratedTestFile(
                filename=name,
                target_module=f.target_module,
                content=_strip_fences(f.content),
            ))

        return TestGenerationResult(files=files, model_notes=result.model_notes)
