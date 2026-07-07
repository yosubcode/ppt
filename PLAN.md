# 교회 주일예배 PPT 자동 생성

## 1. 목표

매주 **주보 PDF + 설교 PDF**를 입력하면, 기존 예배 PPT 템플릿을 수정·조립해 완성 PPT를 만든다.

- 수동 작업: 30~60분
- 목표: 3~5분 (PDF 불러오기 → 확인 → 생성)

**핵심 원칙:** 새 PPT를 처음부터 만들지 않고, 이미 있는 템플릿·찬송가 PPT를 **자동으로 연결·수정**한다.

---

## 2. 현재 구현 상태 (2026-06)

| 기능 | 상태 | 비고 |
|------|------|------|
| GUI (`WorshipPPT.exe`) | ✅ | PDF 불러오기, 필드 수정, PPT 생성 |
| 주보 PDF 자동 분석 | ✅ | 11am 왼쪽 열만 사용 |
| 설교 PDF 자동 분석 | ✅ | 제목, 3부, 성경 구절 |
| 템플릿 플레이스홀더 치환 | ✅ | `ppt_builder.py` (python-pptx) |
| 한국어 → 영어 자동 번역 | ✅ | 설교 제목/3부, 교독문 영문 |
| 찬송가 PPT 삽입 | ✅ | PowerPoint COM, `WORSHIP HYMN` 마커 |
| **찬송 배경 이미지 (`input_hyms/`)** | ✅ | GUI 찾아보기, 투명도 35%/70% |
| **고정 배경 슬라이드 34–36** | ✅ | **플레이스홀더 치환 직후** 적용 (아래 11.3) |
| 찬송 삽입 슬라이드 흰 배경 | ✅ | 배경 이미지 **미선택** 시 (마스터 배경 OFF) |
| 교독문 슬라이드 생성 | ✅ | 한 줄 = 1슬라이드, `{{RES_*}}` 템플릿 |
| **교독문 본문 자동 로드** | ✅ | `responsive_readings/{번호}.txt` |
| **교독문 슬라이드 `( )` 제거** | ✅ | 슬라이드 출력 시 괄호 전체 제거 |
| 성경 본문 1절=1슬라이드 | ✅ | KO/EN, `{{VERSE_*}}` 템플릿 |
| 성경 본문 자동 fetch | ✅ | 개역개정(bskorea) + ESV API |
| **성경/설교 구절 Malgun Gothic** | ✅ | `scripture_merger.py` |
| **COM 저장 시 폰트 embed** | ✅ | `save_presentation_with_embedded_fonts()` |
| **Sunday 템플릿 폰트 통일** | ✅ | `scripts/update_sunday_template_font.py` |
| 설교 part 성경 구절 토큰 | ✅ | `{{VERSE_KO1~3}}`, `{{VERSE_EN1~3}}` |
| 개역개정 띄어쓰기 정규화 | ✅ | bskorea HTML `<font>` 태그 제거 시 조사 붙임 |
| 줄바꿈 단어 분리 방지 | ✅ | 성경 KO/EN, 교독문 KO/EN (COM 후처리) |
| 성경 EN bottom-align | ✅ | 템플릿 EN textbox 밑줄 기준 고정 |
| 마지막 구절 `[Altogether]` | ✅ | EN 바로 위에 배치 |
| Youth Sermon 슬라이드 | ✅ | 없으면 슬라이드 **삭제** (`sermon_title2` 비어 있을 때) |
| 썸네일 PPT 생성 | ✅ | `Thumbnail_Template.pptx` (기본 ON) |
| PyInstaller exe 빌드 | ✅ | `build_exe.bat` |
| `.gitignore` (생성물/비밀) | ✅ | output, exe, .env, extracted JSON 등 |
| 광고 슬라이드 자동 생성 | ⬜ | Phase 10 |
| ESV 저작권 표기 자동 | ⬜ | Phase 11 |

---

## 3. 폴더 구조

```
PPT/
├── PLAN.md
├── requirements.txt
├── worship_ppt.spec              # PyInstaller 설정
├── build_exe.bat                 # exe 빌드
├── run_gui.bat                   # exe 또는 python GUI 실행
├── WorshipPPT.exe                # 빌드 결과 (gitignore)
├── .gitignore
│
├── config/
│   ├── .env                      # API 키 (gitignore)
│   └── extracted_week.json       # PPT 생성 시 저장 (gitignore)
│
├── templates/
│   ├── Sunday_Template.pptx      # 주일예배 템플릿 (720×405pt, Malgun Gothic)
│   └── Thumbnail_Template.pptx   # 썸네일 템플릿
│
├── input/                        # 주보 PDF
├── input2/                       # 설교 PDF
├── input_hyms/                   # 찬송 배경 이미지 (jpg/png 등, GUI에서 선택)
├── hymns/                        # 찬송가 PPT 라이브러리 (~600곡)
├── responsive_readings/          # 성시교독 1–137번 한국어 본문 (.txt)
│   ├── README.md
│   ├── 1.txt … 137.txt
│   └── (한 줄 = 슬라이드 1장)
├── output/                       # 생성 결과 (gitignore)
│   ├── {date}_주일예배.pptx
│   └── {date}_thumbnail.pptx
│
├── scripts/
│   ├── run_gui.py
│   ├── create_sample_template.py
│   ├── scan_placeholders.py
│   ├── verify_pdf_parser.py
│   ├── verify_hymn_insert.py
│   ├── update_sunday_template_font.py   # 템플릿 전체 → Malgun Gothic
│   ├── check_responsive_duplicates.py   # responsive_readings 100–137 중복 검사
│   ├── test_ko_html_spacing.py
│   ├── test_en_verse_split.py
│   ├── test_esv_bracket_split.py
│   ├── test_responsive_parser.py        # 교독문 ( ) 제거 검증
│   ├── test_responsive_library.py
│   ├── test_font_embed_scripture.py     # embed 저장 + Malgun Gothic 검증
│   ├── test_hymn_background.py          # 찬송 배경 상수/경로 단위 테스트
│   ├── test_hymn_background_integration.py  # COM 통합 (34–36 + hymn1/2)
│   ├── test_sermon_verse_parser.py
│   └── test_sermon_verse_output.py
│
└── src/
    ├── main_gui.py               # exe 진입점
    ├── gui_app.py                # Tkinter GUI (+ 찬송 배경 찾아보기)
    ├── week_generator.py         # CLI/GUI 공통 생성 로직
    ├── generate.py               # CLI 진입점
    ├── app_paths.py              # 경로, .env, input_hyms 폴더 생성
    ├── pdf_parser.py             # PDF → JSON 추출
    ├── ppt_builder.py            # 플레이스홀더 치환
    ├── ppt_com_text.py           # COM 텍스트 치환 + embed 저장
    ├── translator.py             # 한→영 번역
    ├── hymn_resolver.py          # 찬송가 파일 찾기
    ├── hymn_merger.py            # 찬송가 삽입 + 배경 (18/46/삽입분)
    ├── responsive_parser.py      # 교독문 줄 분리 + ( ) 제거
    ├── responsive_library.py     # responsive_readings/{n}.txt 자동 로드
    ├── responsive_merger.py      # 교독문 슬라이드 삽입
    ├── scripture_parser.py       # 성경 구절 파싱·절 분리
    ├── scripture_merger.py       # 성경 구절 슬라이드 + Malgun Gothic
    ├── sermon_verse_merger.py    # 설교 part {{VERSE_KO/EN1~3}} COM 치환
    ├── bible_books.py            # 성경 약어 → 전체 이름
    ├── bible_fetcher.py          # 개역개정/ESV 본문 fetch
    ├── thumbnail_builder.py      # 썸네일 PPT
    ├── youth_sermon_merger.py    # Youth Sermon 슬라이드 유지/삭제
    └── korean_text.py            # 한글 텍스트 정규화 (kiwipiepy)
```

---

## 4. 사용법

### 4.1 설치 (개발 환경, 최초 1회)

```powershell
pip install -r requirements.txt
```

필요 환경:

- **Windows**
- **Microsoft PowerPoint** (찬송가·성경·교독문·배경 COM 처리)
- 인터넷 (성경 본문 fetch, 번역)

### 4.2 API 키 설정 (`config/.env`)

```env
ESV_API_KEY=your_esv_token_here
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4.1-mini
```

| 변수 | 용도 |
|------|------|
| `ESV_API_KEY` | 영어 성경 본문 (ESV API, [api.esv.org](https://api.esv.org)) |
| `OPENAI_API_KEY` | 설교/교독문 영문 번역, ESV fallback |
| `OPENAI_MODEL` | OpenAI 모델 (선택) |

- `ESV_API_KEY` 없으면 영어 성경은 bible-api.com **WEB** fallback
- exe 사용 시: `WorshipPPT.exe` 옆 `config/.env`에 동일하게 배치
- 앱 시작 시 `app_paths.load_app_env()`로 자동 로드

### 4.3 GUI (권장)

**1.** `input/`에 주보 PDF, `input2/`에 설교 PDF 넣기

**2.** (선택) `input_hyms/`에 찬송 배경 이미지 넣기

**3.** `WorshipPPT.exe` 실행 (또는 `run_gui.bat` / `python scripts/run_gui.py`)

- `input/` + `input2/` 둘 다 PDF 있으면 시작 시 자동 불러오기
- 왼쪽: 교독문·성경 본문(KO/EN) 붙여넣기/수정
- 오른쪽: 추출 필드 확인, 옵션, **찬송 배경 이미지 찾아보기**, PPT 생성, 로그

**4.** 결과

```
output/{date}_주일예배.pptx
output/{date}_thumbnail.pptx
config/extracted_week.json
```

### 4.4 exe 빌드

```powershell
.\build_exe.bat
```

또는:

```powershell
python -m PyInstaller worship_ppt.spec --distpath . --workpath build\pyinstaller --clean -y
```

코드 수정 후 exe에 반영하려면 **반드시 재빌드** 필요.

### 4.5 CLI

`--from-pdf` 또는 `--json` 중 **하나는 필수**.

```powershell
python src/generate.py --from-pdf
python src/generate.py --from-pdf --json config/extracted_week.json
python src/generate.py --json config/extracted_week.json
```

**CLI 옵션**

| 옵션 | 설명 |
|------|------|
| `--from-pdf` | input/input2 PDF에서 데이터 추출 |
| `--json PATH` | JSON 로드 또는 PDF 데이터 위에 병합 |
| `--no-translate` | 영문 자동 번역 끄기 |
| `--no-hymns` | 찬송가 삽입 끄기 |
| `--no-responsive` | 교독문 슬라이드 끄기 |
| `--no-scripture` | 성경 구절 슬라이드 끄기 |
| `--output PATH` | 출력 파일 경로 지정 |
| `--save-json PATH` | 추출 JSON 저장 경로 |

---

## 5. 데이터 형식

### 5.1 PDF에서 자동 추출되는 필드

**주보 PDF (1페이지 왼쪽 열, 11am 예배)**

| 필드 | 예시 | 비고 |
|------|------|------|
| `date` | `2026-06-07` | ISO |
| `today_date` | `6.7.2026` | 표시용 |
| `hymn1` | `9장` | 대표기도 앞 찬송 |
| `responsive` | `137번` | 번호만 → `responsive_readings/137.txt` 자동 로드 |
| `prayer` | `장우택 장로` | 대표기도 |
| `sermon_title2` | Youth Sermon 제목 | 있으면 유지, 없으면 슬라이드 삭제 |
| `scripture` | `수14:6-15` | 성경봉독 |
| `sermon_title` | `갈렙의 신앙` | |
| `hymn2` | `546장` | |
| `pastor` | `박맹준 목사` | 설교자 |
| `benediction` | `박맹준 목사` | 축도 |

**설교 PDF**

| 필드 | 내용 |
|------|------|
| `sermon_title` | 설교 제목 (주보에 없을 때) |
| `scripture` | 성경 구절 (주보에 없을 때) |
| `sermon_part1` ~ `3` | 설교 3부 제목 |
| `sermon_part1_desc` ~ `3_desc` | 설교 3부 설명 |
| `verse_ko1~3`, `verse_en1~3` | 설교 part별 성경 구절 (fetch/수동) |

주보와 설교 PDF 값이 겹치면 **주보 우선**.

### 5.2 수동 입력 필드 (GUI)

| 필드 | 설명 |
|------|------|
| `responsive_ko_text` | 교독문 한국어 전체 (한 줄 = 슬라이드 1장). 비어 있으면 `responsive_readings/{번호}.txt` 사용 |
| `scripture_ko_text` | 성경 한국어 본문 (절마다 `\n\n` 또는 한 줄 = 한 절) |
| `scripture_en_text` | 성경 영어 본문 |
| `hymn_background_image` | GUI에서 선택한 `input_hyms/` 이미지 경로 (`GenerateOptions`) |

GUI에 본문이 이미 있으면 API fetch를 건너뜀.

### 5.3 `extracted_week.json`

PPT 생성 시 `config/extracted_week.json`에 전체 데이터 저장 (디버그·재사용용). gitignore 대상.

---

## 6. 플레이스홀더

프로그램은 PPT 전체에서 **토큰 문자열**을 찾아 치환한다.  
**슬라이드 번호가 매주 달라져도 OK** (토큰/마커 텍스트로 검색).

### 6.1 주일예배 템플릿 (`Sunday_Template.pptx`)

| JSON 필드 | PPT 토큰 | 용도 |
|-----------|----------|------|
| `today_date` | `{{today_date}}` | 날짜 표시 |
| `prayer` | `{{PRAYER}}` | 대표기도 |
| `pastor` | `{{PASTOR}}` | 설교자 |
| `benediction` | `{{BENEDICTION}}` | 축도 |
| `responsive` | `{{RES}}` | 교독문 번호 |
| `hymn1` | `{{HYMN1}}` | 찬송가 1 |
| `hymn2` | `{{HYMN2}}` | 찬송가 2 |
| `scripture_reference` | `{{SCRIPTURE_REFERENCE}}` | 성경봉독 (영문 ref) |
| `scripture_ko` | `{{SCRIPTURE_KO}}` | 성경봉독 (한글) |
| `scripture_en` | `{{SCRIPTURE_EN}}` | 성경봉독 (영문) |
| `sermon_title` | `{{SERMON_TITLE}}` | 설교 제목 |
| `sermon_title_eng` | `{{SERMON_TITLE_ENG}}` | 설교 제목 영문 |
| `sermon_title2` | `{{SERMON_TITLE2}}` | Youth Sermon |
| `sermon_part1~3` | `{{SERMON_PART1~3}}` | 설교 3부 |
| `sermon_part1~3_desc` | `{{SERMON_PART1~3_DESC}}` | 설교 3부 설명 |
| `sermon_part1~3_eng` | `{{SERMON_PART1~3_ENG}}` | 설교 3부 영문 |
| `verse_ko1~3` | `{{VERSE_KO1~3}}` | 설교 part 성경 (한글) |
| `verse_en1~3` | `{{VERSE_EN1~3}}` | 설교 part 성경 (영문) |

매핑 정의: `src/ppt_builder.py` → `PLACEHOLDER_MAP`

### 6.2 썸네일 템플릿 (`Thumbnail_Template.pptx`)

| 필드 | 토큰 |
|------|------|
| 날짜 | `{{THUMBNAIL_DATE}}` |
| 설교 제목 | `{{SERMON_TITLE}}` |
| 성경 (한글) | `{{SCRIPTURE_KO}}` |
| 설교자 | `{{PASTOR}}` |

### 6.3 동적 슬라이드 토큰

| 구분 | 일반 슬라이드 | 마지막 슬라이드 |
|------|-------------|----------------|
| 교독문 | `{{RES_KO}}`, `{{RES_EN}}` | `{{RES_KO_LAST}}`, `{{RES_EN_LAST}}` |
| 성경 구절 | `{{VERSE_REF}}`, `{{VERSE_KO}}`, `{{VERSE_EN}}` | `{{VERSE_REF_LAST}}`, `{{VERSE_KO_LAST}}`, `{{VERSE_EN_LAST}}` |

- 교독문 템플릿에 KO+EN이 한 shape에 있으면 combined shape로 처리
- 성경 마지막 슬라이드: `[Altogether]` 라벨 shape 고정, EN 위에 배치

### 6.4 템플릿 슬라이드 번호 참고 (고정 번호가 필요한 경우)

| 슬라이드 | 용도 | 비고 |
|---------|------|------|
| **18** | 찬송 1 제목 (`WORSHIP HYMN`, `{{HYMN1}}`) | 마커로도 검색 |
| **34, 35, 36** | **고정 배경 전용** (텍스트 없음) | **반드시 템플릿 번호 기준** (11.3) |
| **46** | 찬송 2 제목 (`WORSHIP HYMN`, `{{HYMN2}}`) | 마커로도 검색 |

> 찬송·교독문·성경 삽입 후 **최종 PPT의 34–36번**은 원래 고정 bg 슬라이드가 **아님**. bg는 슬라이드 객체와 함께 아래로 밀림.

---

## 7. 성경 본문 fetch

### 7.1 한국어 (개역개정)

- 출처: [bskorea.or.kr](https://www.bskorea.or.kr/bible/korbibReadpage.php)
- 방식: HTML 스크래핑 (`version=GAE`)
- 약어 변환: `수14:6-15` → `여호수아 14:6-15` (`bible_books.py`)
- HTML 정리: `<font>` 태그를 **공백 없이** 제거 → `헤브론이`, `여분네의`처럼 조사가 붙은 형태 유지

### 7.2 영어

| 우선순위 | 출처 | 조건 |
|---------|------|------|
| 1 | ESV API | `ESV_API_KEY` in `.env` |
| 2 | OpenAI | ESV 키 없고 `OPENAI_API_KEY` 있을 때 |
| 3 | bible-api.com (WEB) | 둘 다 없을 때 |

ESV API 응답은 `[6]`, `[7]` 인라인 마커 형식 → `scripture_parser.py`에서 절별 분리.

### 7.3 슬라이드 21 표시

- `{{SCRIPTURE_KO}}`: 전체 책 이름 (예: `여호수아 14:6-15`)
- `{{SCRIPTURE_EN}}`: 영문 전체 (예: `Joshua 14:6-15`)

---

## 8. 성경·교독문 슬라이드 COM 삽입

### 8.1 공통 Flow

1. 템플릿 슬라이드에서 토큰 검색 (`{{VERSE_*}}`, `{{RES_*}}`)
2. 필요한 만큼 슬라이드 duplicate
3. PowerPoint COM으로 텍스트 입력 (서식 유지: `ppt_com_text.py`)
4. **단어 분리 방지** 후처리 (8.3)
5. shape 높이·위치 조정
6. **`save_presentation_with_embedded_fonts()`** 로 저장 (8.4)

### 8.2 성경 슬라이드 레이아웃

| shape | 동작 |
|-------|------|
| `{{VERSE_KO}}` | 위쪽 고정, 내용만큼 높이 auto-resize, **Malgun Gothic** |
| `{{VERSE_EN}}` | 템플릿 EN textbox **밑줄(Top+Height) 기준 bottom-align**, **Malgun Gothic** |
| `[Altogether]` (마지막 구절) | EN 바로 위 (14pt gap) |

### 8.3 줄바꿈 단어 분리 방지 (`scripture_merger.py`, `responsive_merger.py`)

PowerPoint 자동 줄바꿈은 한글·영어 모두 줄 중간에서 단어를 자를 수 있다.  
COM 삽입 후 `_prevent_mid_word_line_breaks` 후처리를 **한국어·영어 동일하게** 적용.

**적용 대상:** 성경 KO/EN, 교독문 KO/EN (layout 후 EN 재적용 포함)

### 8.4 폰트 embed 저장 (`ppt_com_text.py`)

```python
save_presentation_with_embedded_fonts(presentation, path)
```

- PowerPoint COM `SaveAs(..., EmbedTrueTypeFonts=msoTrue)`
- 다른 PC에서 열어도 **Malgun Gothic** 레이아웃 유지
- 적용 파일: `scripture_merger.py`, `responsive_merger.py`, `hymn_merger.py`, `youth_sermon_merger.py`, `sermon_verse_merger.py` 등 COM 저장 전부

### 8.5 템플릿 전체 Malgun Gothic 통일

```powershell
python scripts/update_sunday_template_font.py
```

- `Sunday_Template.pptx` 모든 텍스트 shape → **Malgun Gothic** (맑은 고딕)
- 그룹·표·placeholder 포함
- 저장 시 embed fonts 적용

---

## 9. 교독문

### 9.1 본문 소스

| 우선순위 | 소스 |
|---------|------|
| 1 | GUI `responsive_ko_text` (수동 붙여넣기) |
| 2 | `responsive_readings/{번호}.txt` (`responsive_library.py`) |

- 주보에서 **번호만** 추출 (예: `137번`)
- PDF 불러오기 시 `enrich_responsive_data()`가 txt 자동 로드
- `responsive_readings/README.md` 형식: **한 줄 = 슬라이드 1장**

### 9.2 슬라이드 출력 시 `( )` 괄호 제거

`responsive_parser.py` → `strip_responsive_scripture_references()`

- `(다같이)`, `(1 - 6)`, `(마 3 : 16 - 17)` 등 **괄호 안 전체** 제거
- **소스 txt 파일은 수정하지 않음** — 슬라이드에 넣을 때만 제거
- `--no-translate` + 영문 수동 입력 시 영문에도 동일 적용

### 9.3 기타

- 한 줄 = 슬라이드 1장
- 영문: OpenAI ESV-style 번역 (옵션 ON 시)
- 줄바꿈 단어 분리 방지 적용 (8.3)
- `scripts/check_responsive_duplicates.py`: 100–137번 빈 파일·중복 본문 검사

---

## 10. 자동 영문 번역

| 한국어 | 영어 (자동) |
|--------|------------|
| `sermon_title` | `sermon_title_eng` |
| `sermon_part1` + `_desc` | `sermon_part1_eng` |
| `sermon_part2` + `_desc` | `sermon_part2_eng` |
| `sermon_part3` + `_desc` | `sermon_part3_eng` |
| 교독문 각 줄 | ESV-style 영문 |

| 우선순위 | 엔진 |
|---------|------|
| 1 | OpenAI (`OPENAI_API_KEY`) |
| 2 | Google Translate (`deep-translator`) |

- 번역 결과 **첫 글자 대문자** (`Win well` 등)
- `(8절)`, `(verses 10-11)` 등 절 표기 영문에서 제거 (`korean_text.py`)

---

## 11. 찬송가 삽입 및 배경

### 11.1 찬송가 파일 찾기·삽입

```
JSON hymn1: "111장"
  ↓
hymns/ 에서 "111." 로 시작하는 .ppt/.pptx 찾기 (hymn_resolver.py)
  ↓
WORSHIP HYMN 슬라이드 찾기 (번호 고정 아님, 마커 텍스트)
  ↓
placeholder 슬라이드 삭제 (대표기도 / 축도 마커 전까지)
  ↓
찬송가 PPT 슬라이드 InsertFromFile
  ↓
배경 처리 (11.2)
```

- **hymn2 먼저** 삽입 → **hymn1** 삽입 (앞쪽 슬라이드 번호 밀림 방지)
- 찬송가 `.ppt` 가사 = **이미지** (텍스트 아님) → 마스터 배경이 보이면 흐려짐

### 11.2 배경 이미지 (`input_hyms/`)

GUI **찬송 배경 이미지 → 찾아보기** (`gui_app.py` → `GenerateOptions.hymn_background_image`)

| 대상 | 템플릿 기준 | 투명도 | 적용 시점 |
|------|------------|--------|----------|
| **고정 bg** | **34, 35, 36** | **70%** | **플레이스홀더 치환 직후 (11.3)** |
| 찬송 1 제목 | 18 (`WORSHIP HYMN`) | **35%** | 찬송 삽입 시 (마커 검색) |
| 찬송 1 본문 | 18번 **다음** 삽입 슬라이드들 | **70%** | 찬송 삽입 직후 |
| 찬송 2 제목 | 46 (`WORSHIP HYMN`) | **35%** | 찬송 삽입 시 (마커 검색) |
| 찬송 2 본문 | 46번 **다음** 삽입 슬라이드들 | **70%** | 찬송 삽입 직후 |

- 이미지 미선택 → 삽입된 찬송 슬라이드만 **흰색** (`FollowMasterBackground=0`, RGB 255,255,255)
- 18·46번 템플릿 배경은 **수동으로 제거**해 두면, 생성 시 선택 이미지로 다시 적용
- 지원 확장자: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.webp`, `.tif`, `.tiff`
- 구현: `hymn_merger.py` → `_set_image_slide_background()` / `UserPicture` + `Fill.Transparency`

### 11.3 고정 배경 34–36 — **반드시 먼저** (중요)

**왜 먼저인가**

아래 작업들은 슬라이드를 **추가·삭제**해서 34–36 **아래 번호가 밀림**:

| 작업 | 영향 |
|------|------|
| Youth Sermon 없음 | `{{SERMON_TITLE2}}` 슬라이드 **삭제** |
| 교독문 삽입 | ~7장 추가 (줄 수에 따라 변동) |
| 성경 구절 삽입 | ~4장 추가 (절 수에 따라 변동) |
| 찬송 1/2 삽입 | 18·46 이후 대량 추가 |

**잘못된 순서 (과거 버그):** 맨 마지막 `insert_hymns()` 안에서 34–36에 배경 → 그 시점엔 이미 **다른 슬라이드**가 34–36 자리에 있음 (성경/설교 내용 등).

**올바른 순서 (`week_generator.py`):**

```
1. apply_weekly_data()          # 템플릿 복사 + 플레이스홀더 치환
2. apply_fixed_worship_backgrounds_only()  # 34,35,36 → 70% → 저장 ✅
3. youth_sermon_merger          # sermon2 없으면 슬라이드 삭제
4. sermon_verse_merger          # {{VERSE_KO/EN1~3}}
5. responsive_merger            # 교독문 슬라이드 추가
6. scripture_merger             # 성경 슬라이드 추가
7. insert_hymns()               # hymn2 → hymn1, 제목 35% / 본문 70%
```

- `insert_hymns()` 안에서는 **34–36을 더 이상 건드리지 않음**
- bg는 슬라이드 **객체**에 붙어 있으므로 이후 밀림과 함께 이동 (예: 교독문+성경+youth 삭제+hymn1 삽입 후 **~60번대**)

**코드 상수 (`hymn_merger.py`):**

```python
FIXED_BACKGROUND_SLIDE_INDICES = (34, 35, 36)
TITLE_BACKGROUND_TRANSPARENCY = 0.35
CONTENT_BACKGROUND_TRANSPARENCY = 0.70
```

### 11.4 찬송가 배경 — 마스터 배경 OFF (이미지 없을 때)

삽입된 찬송 슬라이드:

1. `FollowMasterBackground = False`
2. `DisplayMasterShapes = False`
3. 배경 → 흰색 단색

(예배 템플릿 장식 배경이 찬송 이미지 뒤로 비치는 문제 해결)

---

## 12. 설교 part 성경 구절 (`sermon_verse_merger.py`)

설교 3부 슬라이드의 토큰:

| 토큰 | JSON 필드 |
|------|-----------|
| `{{VERSE_KO1}}` / `{{VERSE_EN1}}` | `verse_ko1` / `verse_en1` |
| `{{VERSE_KO2}}` / `{{VERSE_EN2}}` | `verse_ko2` / `verse_en2` |
| `{{VERSE_KO3}}` / `{{VERSE_EN3}}` | `verse_ko3` / `verse_en3` |

- COM으로 토큰 치환 (서식 유지)
- `bible_fetcher.enrich_sermon_part_verses()`로 part별 구절 자동 fetch 가능
- embed fonts 저장 적용

---

## 13. 생성 Flow (현재)

```
input/ 주보 PDF + input2/ 설교 PDF
  ↓
pdf_parser.py → 필드 추출 (11am 왼쪽 열)
  ↓
responsive_library.enrich_responsive_data()  # responsive_readings/{n}.txt
  ↓
bible_fetcher.py → 성경 ref + KO/EN 본문 fetch
  ↓
korean_text.normalize_week_sermon_text()   # 띄어쓰기·절 표기 정리
  ↓
GUI 확인 / 교독문·성경 본문 수정 / 찬송 배경 이미지 선택
  ↓
translator.py → _eng 필드 자동 번역
  ↓
ppt_builder.py → 플레이스홀더 치환 (python-pptx)
  ↓
output/{date}_주일예배.pptx 저장
  ↓
[1] hymn_merger.apply_fixed_worship_backgrounds_only()  ← 34,35,36 (70%)
  ↓
COM 삽입 (PowerPoint):
  [2] youth_sermon_merger.py     (Youth Sermon 유지/삭제)
  [3] sermon_verse_merger.py     (설교 part 구절)
  [4] responsive_merger.py       (교독문 + 줄바꿈 후처리)
  [5] scripture_merger.py        (성경 구절 + Malgun Gothic + embed)
  [6] hymn_merger.insert_hymns() (찬송 + 제목/본문 배경)
  ↓
thumbnail_builder.py → output/{date}_thumbnail.pptx
  ↓
config/extracted_week.json 저장
```

---

## 14. GUI 레이아웃

- 창 크기: **1500 × 1000** (최소 960 × 720)
- 좌우 **50:50** grid
- **왼쪽:** 교독문 본문, 성경 본문(KO/EN)
- **오른쪽:** PDF 선택, 옵션, 추출 필드, **찬송 배경 이미지 + 찾아보기**, PPT 생성, 로그
- 폰트: Noto Sans KR (fallback: 맑은 고딕 → Segoe UI)

**옵션 체크박스**

| 옵션 | 기본 |
|------|------|
| 자동 영문 번역 | ON |
| 교독문 슬라이드 생성 | ON |
| 찬송가 슬라이드 삽입 | ON |
| 성경 구절 슬라이드 생성 | ON |
| Youth Sermon 주보 | OFF |

**찬송 배경 이미지**

- 라벨: `찬송 배경 이미지`
- 버튼: `찾아보기` → 기본 폴더 `input_hyms/`
- 생성 로그: `찬송 배경: {파일명} (34-36: 3 slides)`

썸네일 PPT는 `GenerateOptions.generate_thumbnail=True` (기본 ON).

---

## 15. 예배 슬라이드 순서 (참고)

```
묵상기도 → 사도신경 → 교독문 → [찬송1] → 대표기도
→ 성경봉독 → 설교제목 → [성경본문] → [설교 part] → [찬송2]
→ [Youth Sermon] → [광고] → [고정 bg 34–36] → 헌금 → 축도
```

`[ ]` = 동적 삽입·편집 구간

---

## 16. 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| 0 | 템플릿·찬송가·슬라이드 매핑 | ✅ |
| 1 | 플레이스홀더 + JSON 치환 | ✅ |
| 1b | 한→영 자동 번역 | ✅ |
| 2 | 주보/설교 PDF → JSON 추출 | ✅ |
| 3 | 성경 본문 → 슬라이드 + fetch | ✅ |
| 3b | 개역개정 HTML, 줄바꿈 단어 분리 | ✅ |
| 3c | 성경 EN bottom-align, `[Altogether]` | ✅ |
| 4 | 찬송가 COM 삽입 + 흰 배경 | ✅ |
| 4b | **찬송 배경 이미지 (input_hyms)** | ✅ |
| 4c | **고정 bg 34–36 + 적용 순서 fix** | ✅ |
| 5 | 교독문 슬라이드 + 줄바꿈 | ✅ |
| 5b | **responsive_readings 자동 로드** | ✅ |
| 5c | **교독문 ( ) 슬라이드 출력 제거** | ✅ |
| 6 | GUI + exe | ✅ |
| 7 | 썸네일 PPT | ✅ |
| 8 | Youth Sermon, 축도/설교자 | ✅ |
| 8b | **설교 part {{VERSE_*}} 토큰** | ✅ |
| 8c | **Malgun Gothic + embed fonts** | ✅ |
| 8d | **Sunday 템플릿 폰트 통일 스크립트** | ✅ |
| 9 | `.gitignore`, dev artifact 정리 | ✅ |
| 10 | 광고 슬라이드 자동 생성 | ⬜ |
| 11 | ESV 저작권 표기 자동 | ⬜ |

---

## 17. 핵심 라이브러리

| 역할 | 도구 |
|------|------|
| PPT 텍스트 치환 | `python-pptx` |
| PPT 슬라이드 병합·배경·줄바꿈 | PowerPoint COM (`pywin32`) |
| PDF 읽기 | PyMuPDF (`fitz`) |
| 한→영 번역 | `deep-translator` / OpenAI |
| 환경 변수 | `python-dotenv` |
| exe 패키징 | PyInstaller (+ `kiwipiepy_model` 번들) |
| 한글 텍스트 정규화 | `kiwipiepy` (`korean_text.py`) |

---

## 18. 트러블슈팅

| 문제 | 해결 |
|------|------|
| `Permission denied` 저장 실패 | PowerPoint에서 output 파일 닫기 |
| `생성 실패` / COM AttributeError | exe 재빌드 |
| 찬송가 파일 못 찾음 | `hymns/`에 `번호. 제목.ppt` 형식 확인 |
| 영어 성경이 WEB/Yahweh | `config/.env`에 `ESV_API_KEY` 설정 |
| PDF 자동 불러오기 안 됨 | `input/` + `input2/` 둘 다 PDF 필요 |
| 성경 본문 일부만 나옴 | exe 재빌드 (ESV `[n]` 파싱) |
| 한글 `헤브론 이` 띄어쓰기 | bskorea HTML 태그 fix 반영 exe 재빌드 |
| 영어 `f`/`oot` 단어 잘림 | layout 후 word-split 재적용 exe 재빌드 |
| EN/KO 텍스트 겹침 | EN textbox 아래로 이동 |
| 찬송 뒤에 교회 PPT 배경 보임 | 배경 이미지 선택 또는 흰 배경 자동 적용 확인 |
| **34–36 bg가 엉뚱한 슬라이드에** | **코드 순서 확인**: 치환 직후 34–36 적용 여부 (`week_generator.py`) |
| **최종 PPT 34–36번에 bg 없음** | **정상**: 번호가 밀림. bg는 원래 34–36 슬라이드가 이동한 위치에 있음 |
| WorshipPPT.exe 시작 즉시 종료 | `kiwipiepy_model` 번들 + `config/error.log` 확인 |
| API 키 안 읽힘 | exe 옆 `config/.env`, 앱 재시작 |

---

## 19. 대화 세션 구현 변경 이력 (전체)

아래는 이 프로젝트 대화에서 **수정·추가**된 항목 전체 목록이다.

### 19.1 찬송 슬라이드 흰 배경 (마스터 배경 OFF)

- **문제:** 찬송가 `.ppt` 가사 = 이미지인데, 삽입 슬라이드가 `FollowMasterBackground=-1` → 예배 템플릿 장식이 뒤로 보임
- **수정:** `hymn_merger.py` — 삽입 직후 흰색 단색, 마스터 배경/장식 OFF
- **파일:** `src/hymn_merger.py`

### 19.2 찬송 배경 이미지 (`input_hyms/`)

- **추가:** `input_hyms/` 폴더 (`app_paths.ensure_app_dirs`, exe 옆 자동 생성)
- **GUI:** `찬송 배경 이미지` + `찾아보기` (`gui_app.py`)
- **옵션:** `GenerateOptions.hymn_background_image` (`week_generator.py`)
- **적용:** `hymn_merger.py`
  - 18·46 제목: 35%
  - 삽입 찬송 슬라이드: 70%
  - 34–36: 70% (아래 19.4에서 순서 수정)
- **테스트:** `scripts/test_hymn_background.py`, `scripts/test_hymn_background_integration.py`
- **exe:** WorshipPPT.exe 재빌드 반영

### 19.3 고정 배경 34–36 적용 순서 수정 (버그 fix)

- **문제:** `insert_hymns()` 맨 끝에서 34–36 적용 → 그 전에 교독문(+7)·성경(+4)·Youth Sermon 삭제로 **번호 밀림** → 성경/설교 슬라이드에 bg가 들어가고, 원래 bg 슬라이드는 미적용
- **수정:**
  - `week_generator.py`: `apply_fixed_worship_backgrounds_only()`를 **플레이스홀더 치환 직후** 실행
  - `hymn_merger.insert_hymns()`: 34–36 처리 **제거** (hymn1/2만)
- **검증:** 통합 테스트 — minimal `(49,50,51)`, full pipeline `(60,61,62)` 등

### 19.4 COM 저장 시 폰트 embed + Malgun Gothic

- **추가:** `ppt_com_text.save_presentation_with_embedded_fonts()` — `EmbedTrueTypeFonts=msoTrue`
- **수정:** `scripture_merger.py` — `SCRIPTURE_FONT_NAME = "Malgun Gothic"`, KO/EN COM 텍스트에 적용
- **적용:** 모든 COM merger 저장 경로
- **테스트:** `scripts/test_font_embed_scripture.py`

### 19.5 Sunday Template 폰트 통일

- **추가:** `scripts/update_sunday_template_font.py`
- **내용:** `Sunday_Template.pptx` 전 shape → Malgun Gothic (167 shapes, 82 slides), embed 저장
- **목적:** 다른 PC에서도 동일 레이아웃

### 19.6 교독문 슬라이드 `( )` 괄호 제거

- **수정:** `responsive_parser.py` — `strip_responsive_scripture_references()`
- **동작:** `(다같이)`, `(마 3:16-17)` 등 슬라이드 **출력 시** 제거
- **유지:** `responsive_readings/*.txt` 원본은 그대로
- **테스트:** `scripts/test_responsive_parser.py`

### 19.7 교독문 본문 자동 로드 (`responsive_readings/`)

- **추가:** `responsive_readings/1.txt` … `137.txt`, `README.md`
- **추가:** `src/responsive_library.py` — `enrich_responsive_data()`
- **동작:** 주보 `137번` → `137.txt` → GUI `responsive_ko_text` 자동 채움
- **검사:** `scripts/check_responsive_duplicates.py` (100–137 빈 파일·중복)
- **테스트:** `scripts/test_responsive_library.py`

### 19.8 설교 part 성경 구절 토큰

- **추가:** `src/sermon_verse_merger.py`
- **토큰:** `{{VERSE_KO1~3}}`, `{{VERSE_EN1~3}}`
- **연동:** `bible_fetcher.enrich_sermon_part_verses()`, `week_generator` COM 단계
- **테스트:** `scripts/test_sermon_verse_parser.py`, `scripts/test_sermon_verse_output.py`

### 19.9 Youth Sermon 슬라이드 삭제

- **파일:** `youth_sermon_merger.py`
- **동작:** `sermon_title2` 비어 있으면 `{{SERMON_TITLE2}}` 슬라이드 **Delete**
- **영향:** 이후 슬라이드 번호 -1 → **34–36 bg는 치환 직후 적용**해야 밀림과 무관

### 19.10 `.gitignore` 및 dev artifact 정리

- **추가/수정:** `.gitignore`
  - `config/.env`, `config/extracted_week.json`
  - `output/*`, `WorshipPPT.exe`, `build/`
  - 루트 `*.pptx` (templates 제외)
- **삭제:** 불필요 build artifact, dev-only 검증 JSON 등 (대화 중 정리)

### 19.11 GUI / exe 관련 (대화 중 누적)

- Tkinter GUI (`gui_app.py`, `week_generator.py` 공통 로직)
- PyInstaller `WorshipPPT.exe` (~160MB)
- `kiwipiepy_model` exe 번들 (크래시 fix)
- PDF 찾기/불러오기 분리, 백그라운드 파싱, 창 크기 고정
- 성경 본문 bulk KO/EN 붙여넣기 + 자동 절 분리
- PPT 생성 버튼 하단 고정
- 한국어 inline EN verse splitting fix

### 19.12 테스트 스크립트 목록

| 스크립트 | 검증 내용 |
|---------|----------|
| `test_hymn_background.py` | 34–36 인덱스, 투명도 상수 |
| `test_hymn_background_integration.py` | 전체 COM 생성 + bg 위치 (minimal/full) |
| `test_font_embed_scripture.py` | embed + Malgun Gothic |
| `test_responsive_parser.py` | ( ) 괄호 제거 |
| `test_responsive_library.py` | txt 자동 로드 |
| `test_sermon_verse_parser.py` | part 구절 파싱 |
| `test_sermon_verse_output.py` | part 구절 PPT 출력 |
| `check_responsive_duplicates.py` | 100–137 중복·빈 파일 |

### 19.13 권장 git commit 메시지 (대화 중 사용)

```
git commit -m "Embed fonts on save and use Malgun Gothic for scripture verse layout portability"
git commit -m "Strip all parenthetical markers from responsive reading slide output"
git commit -m "Unify Sunday_Template.pptx fonts to Malgun Gothic across all slides"
git commit -m "Add GUI-selected hymn background images for slides 18/46, inserted hymns, and 34-36"
git commit -m "Apply hymn background to slides 34-36 before responsive, scripture, and hymn insertion"
```

---

## 20. 한 줄 요약

> **PDF 넣기 → WorshipPPT.exe → [찬송 bg 선택] → [PPT 생성] → 완성**  
> 주보/설교 추출 + 성경 fetch + 영문 번역 + **34–36 bg 먼저** + 교독문/성경/찬송 COM + embed fonts + 썸네일까지 자동.
