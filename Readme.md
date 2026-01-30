# 🧬 BioDiscovery AI - Technical Documentation

## 📋 Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Data Pipeline](#data-pipeline)
4. [Data Sources](#data-sources)
5. [Collection Robots](#collection-robots)
6. [Preprocessing](#preprocessing)
7. [Vectorization](#vectorization)
8. [Qdrant Storage](#qdrant-storage)
9. [Search Workflow](#search-workflow)

---

## Overview

**BioDiscovery AI** is a multimodal search system for computational biology. It enables simultaneous search across:

- 🧬 **Proteins** (sequences, functions)
- 📄 **Articles** (PubMed, scientific literature)
- 🖼️ **Images** (KEGG pathways, HPA)
- 🧪 **Experiments** (GEO datasets)
- 🔬 **Structures** (PDB, AlphaFold)

### Key Features

- **Multimodal Search**: Text + Sequence + Image + Structure
- **Hybrid Vectorization**: Dense (semantic) + Sparse (lexical)
- **Bridge LLM**: Optimized query generation per collection
- **Design Assistant**: Research candidate suggestions

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  SearchBar → ResultsPanel → EntityModal → DesignAssistant       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                           │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │   Routes    │──▶│  Workflow   │──▶│   Nodes     │           │
│  │  /recommend │   │  LangGraph  │   │ Input→Search│           │
│  └─────────────┘   └─────────────┘   │ →Rank→Enrich│           │
│                                       └─────────────┘           │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │  Encoders   │   │ LLM Client  │   │   Qdrant    │           │
│  │ Text/Seq/Img│   │   Gemini    │   │   Client    │           │
│  └─────────────┘   └─────────────┘   └─────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     QDRANT (Vector DB)                          │
│  Collections: proteins, articles, images, experiments, structures│
│  Vectors: Dense (768d) + Sparse (BM25-like)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Pipeline

The data pipeline consists of 4 main stages:

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 1. COLLECT   │──▶│ 2. PREPROCESS│──▶│ 3. VECTORIZE │──▶│ 4. INDEX     │
│   (Robots)   │   │  (Cleaning)  │   │  (Encoders)  │   │  (Qdrant)    │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

### Stage 1: Automatic Collection

```bash
python scripts/data_collect.py --query "BRCA1 breast cancer" --all
```

### Stage 2: Preprocessing

```bash
python scripts/preprocess_data.py --all
```

### Stage 3-4: Vectorization and Indexing

```bash
python scripts/index_data.py
```

---

## Data Sources

### 📄 Articles - PubMed

| Field | Source | Description |
|-------|--------|-------------|
| `pmid` | PubMed | Unique identifier |
| `title` | PubMed | Article title |
| `abstract` | PubMed | Summary |
| `authors` | PubMed | Author list |
| `journal` | PubMed | Journal name |
| `doi` | PubMed | Digital Object Identifier |

**API used**: NCBI E-utilities (esearch, efetch)

### 🧬 Proteins - UniProt

| Field | Source | Description |
|-------|--------|-------------|
| `uniprot_id` | UniProt | Identifier (e.g., P38398) |
| `protein_name` | UniProt | Full name |
| `gene_names` | UniProt | Associated genes |
| `sequence` | UniProt | Amino acid sequence |
| `function` | UniProt | Functional description |
| `organism` | UniProt | Organism |

**API used**: UniProt REST API

### 🖼️ Images - KEGG / HPA

| Field | Source | Description |
|-------|--------|-------------|
| `source` | - | "KEGG" or "HPA" |
| `caption` | KEGG/HPA | Caption |
| `description` | KEGG/HPA | Detailed description |
| `file_path` | Local | Path to image file |
| `url` | KEGG/HPA | External URL |

**Sources**:
- KEGG: Biological pathways (hsa05224, etc.)
- HPA: Human Protein Atlas (immunofluorescence)

### 🧪 Experiments - GEO

| Field | Source | Description |
|-------|--------|-------------|
| `accession` | GEO | GSE ID (e.g., GSE12345) |
| `title` | GEO | Dataset title |
| `summary` | GEO | Description |
| `organism` | GEO | Organism |
| `n_samples` | GEO | Number of samples |
| `measurements` | Generated | Expression data |

**API used**: NCBI E-utilities (GDS database)

**Note**: The `measurements` are randomly generated for demonstration. In production, they would come from parsing SOFT/MINiML files.

### 🔬 Structures - PDB / AlphaFold

| Field | Source | Description |
|-------|--------|-------------|
| `pdb_id` | PDB | PDB identifier (e.g., 1TSR) |
| `alphafold_id` | AlphaFold | AF identifier |
| `title` | PDB | Title |
| `method` | PDB | Method (X-ray, cryo-EM) |
| `resolution` | PDB | Resolution in Å |
| `file_path` | Local | Path to .pdb file |

**APIs used**:
- RCSB PDB REST API
- AlphaFold Database API

---

## Collection Robots

### Robot Structure

```python
class RobotPapers:
    """Collects PubMed articles"""
    def collect(query: str, max_results: int) -> int

class RobotSequences:
    """Collects UniProt proteins"""
    def collect(query: str, organism: str, max_results: int) -> int

class RobotImages:
    """Collects KEGG images"""
    def collect() -> int

class RobotExperiments:
    """Collects GEO datasets"""
    def collect(genes: List[str], keywords: List[str]) -> int

class RobotStructures:
    """Collects PDB + AlphaFold structures"""
    def collect(query: str, max_results: int) -> int
    def collect_alphafold_from_proteins(max_results: int) -> int
```

### Usage

```bash
# Collect everything
python data_collect.py --query "BRCA1 breast cancer" --all

# Specific collections
python data_collect.py --query "TP53 cancer" --papers --sequences

# With limit
python data_collect.py --query "Alzheimer" --all --max 50
```

---

## Preprocessing

### Required Fields per Collection

| Collection | Required Fields |
|------------|-----------------|
| proteins | `uniprot_id`, `protein_name`, `sequence` |
| articles | `title`, `abstract` |
| images | `caption`, `source`, (`file_path` OR `url`) |
| experiments | `accession`, `title` |
| structures | `title`, (`pdb_id` OR `alphafold_id`) |

### Preprocessing Script

```bash
# Validate without modifying
python preprocess_data.py --all --validate-only

# Clean (removes invalid entries)
python preprocess_data.py --all
```

### Preprocessing Actions

1. **Validation**: Checks required fields
2. **Enrichment**: Adds `normalized_bridge` if missing
3. **Cleaning**: Removes invalid documents
4. **Backup**: Creates backup before modification

---

## Vectorization

### Encoders Used

| Type | Model | Dimension | Description |
|------|-------|-----------|-------------|
| **Text** | BGE-base-en-v1.5 | 768 | Semantic embeddings |
| **Sequence** | ESM2-650M | 1280 | Protein embeddings |
| **Image** | BiomedCLIP | 512 | Biomedical embeddings |
| **Sparse** | BM25-like | Variable | Lexical vectors |

### Hybrid Vectorization

Each document is encoded into two vectors:

```python
# Dense: Captures semantics
dense_vector = text_encoder.encode(text)  # [768 dims]

# Sparse: Captures exact terms
sparse_vector = sparse_encoder.encode(text)  # {term_id: weight}
```

### Encoded Text per Collection

| Collection | Encoded Text |
|------------|--------------|
| proteins | `protein_name + function` |
| articles | `title + abstract` |
| images | `caption + description` |
| experiments | `title + summary` |
| structures | `title` |

### Code Example

```python
from app.core.encoders import MultiModalEncoder

encoder = MultiModalEncoder()

# Text
text_vector = encoder.encode_text("BRCA1 breast cancer")
# → {"dense": [0.12, -0.34, ...], "sparse": {"BRCA1": 0.8, "cancer": 0.6}}

# Sequence
seq_vector = encoder.encode_sequence("MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTK")
# → [0.23, -0.45, ...]

# Image
img_vector = encoder.encode_image("pathway.png")
# → [0.11, 0.67, ...]
```

---

## Qdrant Storage

### Collection Structure

```
Qdrant Server (localhost:6333)
│
├── proteins
│   ├── vector: text (768d)
│   ├── vector: sequence (1280d)
│   ├── sparse: text_sparse
│   └── payload: {uniprot_id, protein_name, sequence, ...}
│
├── articles
│   ├── vector: text (768d)
│   ├── sparse: text_sparse
│   └── payload: {pmid, title, abstract, ...}
│
├── images
│   ├── vector: caption (768d)
│   ├── vector: image (512d)
│   ├── sparse: caption_sparse
│   └── payload: {source, caption, file_path, ...}
│
├── experiments
│   ├── vector: text (768d)
│   ├── sparse: text_sparse
│   └── payload: {accession, title, measurements, ...}
│
└── structures
    ├── vector: text (768d)
    ├── sparse: text_sparse
    └── payload: {pdb_id, title, method, ...}
```

### Hybrid Search

Qdrant uses RRF (Reciprocal Rank Fusion) to combine:

```python
# Hybrid search
results = qdrant.query(
    collection="proteins",
    query={
        "dense": dense_vector,
        "sparse": sparse_vector
    },
    fusion="rrf",  # Rank fusion
    limit=10
)
```

### Collection Configuration

```python
# Creating a collection
qdrant.create_collection(
    name="proteins",
    vectors={
        "text": {"size": 768, "distance": "Cosine"},
        "sequence": {"size": 1280, "distance": "Cosine"}
    },
    sparse_vectors={
        "text_sparse": {}  # BM25-like
    }
)
```

---

## Search Workflow

### The 3 Search CASES

| CASE | Input | Strategy |
|------|-------|----------|
| **CASE 1** | Text only | Direct parallel search |
| **CASE 2** | Modal only | Modal search → Bridge LLM |
| **CASE 3** | Text + Modal | Hybrid search (NO FUSION) |

### Architecture v3.3 - NO FUSION

```
┌─────────────────────────────────────────────────────────────┐
│                     CASE 3 - NO FUSION                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Text ───────┐                                              │
│              │                                              │
│              ▼                                              │
│         ┌─────────┐      ┌─────────────┐                   │
│         │ Encode  │─────▶│ Search ALL  │──▶ Results        │
│         │  Text   │      │ Collections │                   │
│         └─────────┘      └─────────────┘                   │
│                                                             │
│  Modal ──────┐                                              │
│  (seq/img)   │                                              │
│              ▼                                              │
│         ┌─────────┐      ┌─────────────┐                   │
│         │ Encode  │─────▶│ Search OWN  │──▶ Modal Results  │
│         │ Modal   │      │ Collection  │                   │
│         └─────────┘      └─────────────┘                   │
│                                                             │
│                     ┌─────────────┐                         │
│                     │   MERGE     │──▶ Final Results       │
│                     │  (NO FUSION)│                         │
│                     └─────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### Workflow Nodes

1. **INPUT_NODE**: Detects inputs and encodes vectors
2. **SEARCH_NODE**: Executes searches based on CASE
3. **RANK_NODE**: Applies MMR and generates candidates
4. **OUTPUT_NODE**: Formats response

---

## Quick Start

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Start Qdrant

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 3. Collect data

```bash
python scripts/data_collect.py --query "BRCA1 cancer" --all --max 50
```

### 4. Preprocess

```bash
python scripts/preprocess_data.py --all
```

### 5. Index

```bash
python scripts/index_data.py
```

### 6. Start backend

```bash
uvicorn app.main:app --reload
```

### 7. Start frontend

```bash
cd frontend
npm install
npm run dev
```

---

## File Structure

```
biodiscovery-ai/
├── backend/
│   ├── app/
│   │   ├── api/routes.py           # FastAPI endpoints
│   │   ├── core/
│   │   │   ├── encoders.py         # Vectorization
│   │   │   ├── qdrant_client.py    # Qdrant operations
│   │   │   └── llm_client.py       # Gemini/LLM
│   │   ├── graph/
│   │   │   ├── nodes.py            # Workflow nodes
│   │   │   └── workflow.py         # LangGraph workflow
│   │   └── models/schemas.py       # Pydantic schemas
│   │
│   ├── data/                       # Collected data
│   │   ├── proteins.json
│   │   ├── articles.json
│   │   ├── images.json
│   │   ├── experiments.json
│   │   └── structures.json
│   │
│   └── scripts/
│       ├── data_collect.py         # Data collection
│       ├── preprocess_data.py      # Preprocessing
│       └── index_data.py           # Indexing
│
└── frontend/
    └── src/
        ├── components/             # React components
        ├── stores/                 # Zustand stores
        └── services/api.ts         # API client
```

---

## Author

**BioDiscovery AI** - Multimodal search system for computational biology

---
