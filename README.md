# Fact Knowledge Layer

A robust, generic system for ingesting documents (PDFs), extracting atomic numerical and semantic facts, strictly grounding each fact to verbatim source evidence with exact page numbers and character offsets, and establishing cross-document relationships (corroborations, contradictions, and contextual reconciliations).

---

## Setup and Run Instructions

### Prerequisites
- **Python 3.10+** (tested on Python 3.11 / 3.12)
- **PostgreSQL database** with the [`pgvector`](https://github.com/pgvector/pgvector) extension enabled (e.g., Render PostgreSQL, Supabase, or self-hosted)

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/akkiyolo/fact-knowledge-layer.git
cd fact-knowledge-layer

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory (or copy from `.env.example`):

```ini
# Application
APP_NAME=Fact Knowledge Layer
APP_ENV=development
DEBUG=true
API_HOST=0.0.0.0
API_PORT=8000

# Database (PostgreSQL with pgvector enabled)
DATABASE_URL=postgresql://<USER>:<PASSWORD>@<HOST>:<PORT>/<DATABASE>

# LLM Provider (Google Gemini recommended for high throughput & structured JSON)
LLM_PROVIDER=google
GOOGLE_API_KEY=your_gemini_api_key_here
GOOGLE_MODEL=gemini-3.5-flash-lite

# Embeddings
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSION=384

# Pipeline Thresholds
CLAIM_CONFIDENCE_THRESHOLD=0.70
GROUNDING_CONFIDENCE_THRESHOLD=0.70
MAX_CLAIMS_PER_CHUNK=20
CANDIDATE_TOP_K=10
CANDIDATE_SIMILARITY_THRESHOLD=0.15
ATTRIBUTE_SIMILARITY_THRESHOLD=0.85
```

### 4. Database Initialization
Database tables and pgvector vector indices are created automatically upon FastAPI startup via SQLAlchemy metadata reflection.

### 5. Run the Application
Start the local server:
```bash
python -m uvicorn app.main:app --reload
```

- **Web Dashboard UI:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger REST API:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 6. Evaluating Sample Documents & Pre-populating Graph
To evaluate the starter dataset (`01-delhivery-prospectus-2022-excerpt.pdf`, `02-delhivery-annual-report-fy24-excerpt.pdf`, and `03-delhivery-q4-fy24-earnings-presentation.pdf`) and build the initial cross-document knowledge graph:
```bash
python scripts/evaluate_samples.py
```
Or upload any new PDF directly through the browser UI dropzone at `http://localhost:8000/`.

---

## Video Demo
*Demo Video Link:* [https://www.youtube.com/watch?v=B7apj3Cb674]

The demonstration covers:
1. Drag-and-drop ingestion of a multi-page PDF into the automated extraction pipeline.
2. Inspection of extracted numerical facts and semantic facts with exact page-level grounding and verbatim quotes.
3. Cross-document corroboration detection (e.g. additive employee metrics, segment delivery centres).
4. Automated reconciliation of apparent contradictions through contextual dimensions (`time_scope`, reporting scope).

---

## Approach

### 1. Architecture Overview
The system is architected as an asynchronous, stateful LangGraph pipeline coupled with a FastAPI backend, PostgreSQL + pgvector storage, and a modern glassmorphic web interface.

```
                  ┌────────────────────────────────────────┐
                  │               Input PDF                │
                  └───────────────────┬────────────────────┘
                                      ▼
                        [ 1. Ingestion & Hashing ]
                                      ▼
                      [ 2. Chunking & Layout Parse ]
                                      ▼
                      [ 3. Atomic Fact Extraction ]
                                      ▼
                     [ 4. Strict Evidence Grounding ]
                                      ▼
                    [ 5. Dynamic Canonicalization ]
                                      ▼
                     [ 6. Vector Embedding (384d) ]
                                      ▼
                    [ 7. pgvector Candidate Search ]
                                      ▼
                   [ 8. Relation Classification LLM ]
                                      ▼
                  [ 9. Contextual Reconciliation LLM ]
                                      ▼
                 [ 10. Graph Persistence (PostgreSQL) ]
                                      ▼
                        [ REST API & Web UI ]
```

### 2. Pipeline Stages

#### Stage 1: Document Ingestion & Chunking
- **PyMuPDF Engine:** Extracts layout-aware textual content while tracking exact page boundaries, token lengths, and character spans.
- **Deduplication:** SHA-256 content hashing guarantees idempotency and prevents redundant processing of duplicate documents.
- **Adaptive Chunking:** Sliding window chunks of up to 1,200 tokens with 150-token overlap, preserving surrounding narrative context for isolated financial tables.

#### Stage 2: Atomic Fact Extraction & Strict Evidence Grounding
- **Fact Schema:** Decomposes complex textual paragraphs and tables into atomic factual tuples:
  `{ entity_text, entity_type, attribute_raw, value, unit, time_scope, scope, qualifiers, evidence_text, evidence_page }`.
- **Strict Evidence Grounding:** The extractor must copy the verbatim substring from the source chunk. If the quote cannot be verified or matched within the source text, grounding confidence is penalized or marked unresolved.
- **Native JSON Enforcement:** Uses structured schema validation (`response_mime_type="application/json"`) to eliminate markdown preambles or malformed JSON.

#### Stage 3: Dynamic Attribute Canonicalization
- Solves vocabulary drift across different authoring teams (e.g., "Revenue from customers", "Sales turnover", "Total revenue from operations").
- Uses cosine similarity over normalized embedding vectors to associate raw attributes with canonical concepts dynamically without hardcoded entity dictionaries.

#### Stage 4: Sub-quadratic Cross-Document Candidate Retrieval
- Comparing all claims against all existing claims across an entire corpus is $O(N^2)$ and cost-prohibitive.
- We implement candidate retrieval using **pgvector cosine distance queries**: for each new claim, we retrieve the top-$k$ nearest neighbors from *different* documents above a similarity threshold.
- Domain keyword intersection provides a hybrid boost for financial indicators (revenue, EBITDA, PIN codes, centres, headcount).

#### Stage 5: Two-Stage Relation Classification & Contextual Reconciliation
- **Stage 5A: Classification:** Candidate claim pairs are evaluated by an LLM prompt that determines whether they are `corroborates`, `contradicts`, or `neutral`.
- **Stage 5B: Reconciliation:** Contradictions are routed to a dedicated reconciliation stage. Rather than simply declaring two different values as conflicting, the model examines whether the difference is reconciled by:
  - **`time_scope`**: Different reporting periods (e.g. FY23 vs FY24).
  - **`accounting_basis`**: Sub-segment metric vs total consolidated metric (e.g. traded goods revenue vs total revenue from customers).
  - **`geography_or_population`**: Specific regional subset vs nationwide total.
  When reconciled, the relation is upgraded to `contradicts_reconciled` with an explicit human-readable reconciliation factor.

### 3. Key Decisions & Trade-Offs

| Decision | Chosen Approach | Alternative Considered | Rationale |
| :--- | :--- | :--- | :--- |
| **Fact Granularity** | Atomic claim tuples | Raw chunk embeddings / summaries | Atomic claims enable precise mathematical comparison and field-level contradiction checks. |
| **Candidate Retrieval** | pgvector Cosine Index + Top-$K$ Filtering | All-Pairs Cartesian Product ($N \times M$) | Reduces LLM comparison calls from thousands to the top semantically relevant candidate pairs. |
| **Contradiction Resolution** | Two-step classify $\rightarrow$ reconcile | Single-pass classification | Decoupling classification from reconciliation produces higher accuracy and prevents models from prematurely rationalizing real contradictions. |
| **Model Selection** | `gemini-3.5-flash-lite` | Local Ollama 7B / GPT-4o | Gemini 3.5 Flash Lite provides high rate-limit allowances, low latency, native JSON support, and zero per-token cost for academic evaluations. |
| **Embedding Fallback** | Normalized `HashingVectorizer` fallback | Hard PyTorch dependency | Ensures flawless execution on Windows environments where native C++ DLLs (`c10.dll`) can cause OS-level import crashes. |

### 4. AI & Engineering Tools Used
- **Google Generative AI (`gemini-3.5-flash-lite`)**: Fast, accurate structured fact extraction and relational reasoning.
- **LangGraph**: Stateful graph execution with fault isolation per document chunk.
- **PyMuPDF (fitz)**: Accurate PDF text extraction with exact coordinate and page tracking.
- **PostgreSQL with pgvector**: Production-ready vector indexing alongside relational constraints.
- **FastAPI & Pydantic v2**: High-performance typed REST APIs and strict schema validation.
- **Vanilla Glassmorphic Web UI**: Responsive dark-mode dashboard without heavy JavaScript framework bloat.

---

## Four Required Challenge Cases Handled

The starter dataset consists of three corporate disclosures from Delhivery Limited:
1. `01-delhivery-prospectus-2022-excerpt.pdf` (Initial Public Offering Prospectus, 2022)
2. `02-delhivery-annual-report-fy24-excerpt.pdf` (Integrated Annual Report, FY24)
3. `03-delhivery-q4-fy24-earnings-presentation.pdf` (Q4 FY24 Investor Presentation)

Here is how the system handles the four core challenge requirements:

### 1. Meaningful Numerical Fact Extraction & Grounding
- **Claim:** Delhivery serviced 17,488 PIN codes in India.
- **Entity:** `nation-wide network` | **Attribute:** `PIN codes serviced` | **Value:** `17488 PIN codes`
- **Source Document:** `01-delhivery-prospectus-2022-excerpt.pdf`, Page 52.
- **Grounding Evidence Quote:** *"we serviced 17,488 PIN codes, representing 90.61% of the 19,300 PIN codes in India"*
- **Extraction & Grounding Confidence:** `100%` (Status: `USABLE`).

### 2. Meaningful Semantic Fact Extraction & Grounding
- **Claim:** Purpose and allocation of R&D expenditure by international subsidiaries.
- **Entity:** `Delhivery USA` | **Attribute:** `R&D expenditure purpose`
- **Value:** *"R&D expenditure is being incurred by Delhivery USA, but not in specific technologies to improve the environmental and social impacts of product and processes"*
- **Source Document:** `02-delhivery-annual-report-fy24-excerpt.pdf`, Page 52 (BRSR).
- **Extraction & Grounding Confidence:** `100%` (Status: `USABLE`).

### 3. Cross-Document Corroboration
- **Additive Metric Corroboration:**
  - *Source Claim (Doc 1):* Total delivery centres operated = `3,730`.
  - *Target Claim (Doc 1):* Self-operated centres (`2,521`) + Constellation partner centres (`1,209`).
  - *System Output:* `corroborates` (Confidence: `0.98`).
  - *Explanation:* Total delivery centres (3,730) matches the operational breakdown of 2,521 self-operated centres and 1,209 partner-operated centres.
- **Demographic Employee Corroboration:**
  - *Source Claim (Doc 2):* Total permanent employees = `18,527`.
  - *Target Claim (Doc 2):* Male employees (`17,072`) + Female employees (`1,455`).
  - *System Output:* `corroborates` (Confidence: `0.99`). Exact arithmetic verification across reporting tables.
- **Cross-Document Revenue Alignment:**
  - *Annual Report FY24 Turnover Base* corroborates *Earnings Presentation FY24 Consolidated Revenue* (`₹8,142 Cr`) with shared FY24 financial scope.

### 4. Apparent Contradiction Reconciled Through Context
- **Revenue Apparent Contradiction:**
  - *Claim A (Doc 3):* Revenue from customers = `₹8,142 Cr` (Time Scope: `FY24`).
  - *Claim B (Doc 3):* Revenue from customers = `₹7,225 Cr` (Time Scope: `FY23`).
  - *System Output:* `contradicts_reconciled` (Confidence: `0.94`).
  - *Reconciling Factor:* `time_scope`.
  - *Explanation:* Apparent conflict in total annual revenue is reconciled by distinct fiscal years, accurately identifying a 12.7% YoY top-line expansion.
- **Adjusted EBITDA Turnaround:**
  - *Claim A (Doc 3):* Adjusted EBITDA = `₹76 Cr` (Time Scope: `FY24`).
  - *Claim B (Doc 3):* Adjusted EBITDA = `-₹404 Cr` (Time Scope: `FY23`).
  - *System Output:* `contradicts_reconciled` (Confidence: `0.96`).
  - *Reconciling Factor:* `time_scope`.
  - *Explanation:* Reconciled by financial turnaround and operational leverage achieved between FY23 and FY24.

---

## Limitations and Next Steps

### Current Limitations
1. **Multi-Page Spanning Financial Tables:** Tables split across physical PDF page breaks can occasionally truncate header hierarchies, requiring chunk overlap tuning to reconstruct row context.
2. **Scanned Documents (OCR Requirement):** The pipeline relies on text layout streams from PyMuPDF. Pure image PDFs require an OCR pre-processing step (e.g. Tesseract or Google Cloud Vision) prior to chunking.
3. **Public API Rate Quotas:** Free-tier LLM endpoints enforce 15 Requests-Per-Minute quotas, requiring built-in exponential backoff retry policies during batch candidate processing.

### Next Steps & Future Roadmap
1. **Multimodal Visual Table Ingestion:** Incorporate multimodal vision models to directly parse complex nested charts and infographics without intermediate OCR loss.
2. **Interactive Graph Topology View:** Extend the UI with a full D3.js or Cytoscape force-directed graph allowing visual exploration of cluster communities across dozens of documents.
3. **Human-in-the-Loop Feedback Loop:** Allow domain reviewers to approve, override, or flag relation predictions, updating edge confidence scores through online learning.
4. **Automated Document Delta Summarization:** Synthesize automatic executive briefing memos highlighting key differences and reconciliations whenever an updated report is uploaded.

---

## Additional Notes

- **Zero Document-Specific Hardcoding:** The extraction and relation prompts contain no hardcoded references to Delhivery, logistics terms, or specific financial headers. The pipeline generalizes across medical papers, legal contracts, regulatory filings, and corporate ESG disclosures.
- **Auditability First:** Every fact displayed in the interface retains its lineage: document ID, page number, character offsets, extraction confidence, and grounding confidence.
- **RESTful Architecture:** All backend capabilities are exposed via typed OpenAPI endpoints, making it easy to embed the Fact Knowledge Layer into existing enterprise data pipelines.
