# Incident Analyzer - End-to-End Documentation

## Overview
The Incident Analyzer is a Retrieval-Augmented Generation (RAG) system that processes incident data from Excel files, aggregates incidents by month, stores summaries in a vector database (ChromaDB), and provides an intelligent agent that answers natural language questions about incident trends.

## Architecture

```
Excel Data (incidents.xlsx)
        ↓
Incident Processor (categorizes & aggregates by month)
        ↓
Monthly Summaries
        ↓
    ┌───┴───┐
    ↓       ↓
Pandas   ChromaDB
Tool     Tool (vector store)
    │       │
    └───┬───┘
        ↓
  Agent Executor (LangChain)
        ↓
Google Gemini LLM
        ↓
    User Answer
```

## System Components

### 1. **incident_processor.py**
- Reads Excel incident log
- Categorizes incidents by type
- Aggregates incidents by month
- Generates human-readable monthly summaries

### 2. **chroma_store.py**
- Initializes ChromaDB vector store (in-process, local storage)
- Generates embeddings using HuggingFace sentence-transformers
- Stores monthly summaries with metadata
- Provides similarity search capabilities

### 3. **semantic_chunking_engine.py**
- Splits documents into semantically coherent chunks
- Uses cosine similarity for chunk boundary detection
- Configurable chunk size and overlap
- Preserves context across chunks

### 4. **components/**
- **embeddings.py**: EmbeddingsManager for text vectorization and caching
- **retriever.py**: SemanticRetriever for similarity-based document retrieval
- **document_processor.py**: DocumentProcessor for preparing documents for RAG

### 5. **agent.py**
- Builds LangChain AgentExecutor with two tools:
  - **pandas_analysis_tool**: Query current month data with PandasDataFrameAgent
  - **historical_comparison_tool**: Search similar historical months in ChromaDB
- Integrates Google Gemini as the LLM

### 6. **main.py**
- Orchestration entry point
- Loads incident data from Excel
- Upsets monthly summaries into ChromaDB
- Launches interactive CLI or batch query mode

## Installation & Setup

### Prerequisites
- Python 3.12+
- Google API Key (free tier: https://ai.google.dev)

### Steps

1. **Create Virtual Environment**
```bash
python3.12 -m venv venv_py312
source venv_py312/bin/activate
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Set Up Environment**
```bash
cp .env.example .env
# Edit .env and add your Google API Key:
# GOOGLE_API_KEY=AIza...
```

4. **Run the Program**
```bash
# Interactive mode
python main.py --file incidents.xlsx

# Batch mode (single query)
python main.py --file incidents.xlsx --query "How many incidents this month?"
```

## How It Works - Step by Step

### Step 1: Data Processing
- Reads `incidents.xlsx` with columns: Date, Category, Description, Severity
- Groups incidents by month
- Creates monthly aggregation table with incident counts per category

### Step 2: Embedding & Storage
- Converts each monthly summary to text: "In 2025-05: 15 total incidents..."
- Generates embeddings using local HuggingFace model (sentence-transformers/all-MiniLM-L6-v2)
- Stores embeddings + metadata in ChromaDB (./chroma_db directory)

### Step 3: Agent Building
- Creates two tools:
  1. **Pandas Tool**: Direct SQL-like queries on DataFrames
  2. **Vector Store Tool**: Semantic search on historical summaries
- Integrates Google Gemini LLM with tool-calling capability

### Step 4: Query Processing
- User asks a question in natural language
- Agent decides which tool(s) to use
- Pandas tool answers current month questions
- Vector store tool finds similar historical periods
- LLM synthesizes the answer

---

## Sample Input and Output

### Sample 1: Current Month Analysis

**Input (Interactive)**
```
You: What is the total incident count for this month?
```

**Processing Flow**
1. Agent recognizes "this month" → uses pandas_analysis_tool
2. Pandas agent queries monthly_df for current month row
3. Extracts total count and category breakdown

**Output**
```
Agent: Based on the current month's data (2025-06):
- Total incidents: 47
- Critical: 3
- High: 8
- Medium: 18
- Low: 18

The most common category is "Performance" with 12 incidents.
```

---

### Sample 2: Trend Comparison

**Input (Interactive)**
```
You: How does June compare to May in terms of incident volume?
```

**Processing Flow**
1. Agent recognizes temporal comparison → uses both tools
2. Pandas tool gets June data (current)
3. Vector store tool searches for "May incident summary" 
4. Retrieves top 3 similar historical reports
5. LLM compares and synthesizes

**Output**
```
Agent: June has seen a slight increase compared to May:
- May: 41 incidents
- June: 47 incidents
- Increase: +14.6%

Both months show "Performance" and "Authentication" as top categories.
The severity distribution remains similar, with most incidents being Low-Medium priority.
```

---

### Sample 3: Batch Mode Query

**Command**
```bash
python main.py --file incidents.xlsx --query "Which category had the most incidents across all months?"
```

**Processing Flow**
1. Loads data and initializes agent
2. Executes single query without interactive loop
3. Agent uses pandas_analysis_tool on categorized_df
4. Aggregates across all months

**Output**
```
Agent: Across all available months, "API_Error" is the top category with 156 total incidents.

Top 5 categories:
1. API_Error: 156 incidents
2. Database_Connection: 89 incidents
3. Authentication_Failure: 67 incidents
4. Performance: 45 incidents
5. Configuration: 34 incidents
```

---

## File Structure

```
incident_analyzer/
├── main.py                          # Entry point
├── agent.py                         # Agent configuration & LLM setup
├── incident_processor.py            # Data processing logic
├── chroma_store.py                  # Vector store management
├── semantic_chunking_engine.py      # Document chunking
├── components/
│   ├── __init__.py
│   ├── embeddings.py               # Embeddings manager
│   ├── retriever.py                # Semantic retriever
│   └── document_processor.py        # Document processing
├── requirements.txt                 # Dependencies
├── .env.example                     # Environment template
├── incidents.xlsx                   # Sample data (Excel)
├── chroma_db/                       # ChromaDB storage (auto-created)
└── README.md                        # This file
```

## Configuration

### Environment Variables
```
GOOGLE_API_KEY          # Required: Google Gemini API key
CHROMA_PERSIST_DIR      # Optional: ChromaDB storage path (default: ./chroma_db)
CHROMA_COLLECTION       # Optional: Collection name (default: incident_monthly_summaries)
```

### CLI Arguments
```
--file              # Path to incident Excel file (required)
--sheet             # Sheet name or index in Excel (default: 0)
--no-upsert         # Skip upserting to ChromaDB if already populated
--query             # Run single query in batch mode (no interactive loop)
--model             # LLM model name (default: gemini-1.5-flash)
--milvus-k          # Number of historical reports to retrieve (default: 3)
```

## Key Features

1. **In-Process Vector Store**: No external dependencies or servers needed
2. **Local Embeddings**: All text vectorization happens locally
3. **Semantic Search**: Finds contextually similar incidents across time
4. **Dual Analysis**: Combines structured data queries with semantic search
5. **Interactive & Batch Modes**: Flexible query interface
6. **Persistent Storage**: Monthly summaries cached in ChromaDB

## Troubleshooting

### API Key Issues
- Ensure GOOGLE_API_KEY is set in .env
- Verify key has access to gemini-1.5-flash model
- Get free key at https://ai.google.dev

### ChromaDB Issues
- Delete ./chroma_db directory to reset vector store
- Re-run with data file to rebuild

### Model Download Issues
- First run downloads embeddings model (~80MB)
- Requires internet connection
- Model cached in ~/.cache/huggingface

## Dependencies

- **langchain**: Agent orchestration framework
- **google-generativeai**: Gemini API integration
- **chromadb**: Vector store (in-process)
- **sentence-transformers**: Embedding generation
- **pandas**: Data processing
- **openpyxl**: Excel file reading

## Performance Notes

- First run: ~30s (includes model downloads and ChromaDB initialization)
- Subsequent runs: ~5-10s
- Query response time: 2-5s depending on Gemini API latency

---

## Example Walkthrough

### Full Interactive Session

```
$ python main.py --file incidents.xlsx

2025-06-06 [INFO] Processing incident log: incidents.xlsx
2025-06-06 [INFO] Monthly aggregation complete: 12 months

======================================================================
  MONTHLY INCIDENT AGGREGATION
======================================================================
month      total  Critical  High  Medium  Low
2025-01    42     2         5     15      20
2025-02    38     1         4     16      17
...
2025-06    47     3         8     18      18
======================================================================

2025-06-06 [INFO] Connecting to ChromaDB and upserting monthly summaries...
2025-06-06 [INFO] Upsert complete. 12 documents stored.

2025-06-06 [INFO] Building AgentExecutor...

💬  Incident Analytics Agent — Interactive Mode
    Type your question and press Enter.  Type 'exit' or 'quit' to stop.

You: What's the severity breakdown this month?

Agent: In June 2025:
- Critical (P0): 3 incidents
- High (P1): 8 incidents  
- Medium (P2): 18 incidents
- Low (P3): 18 incidents

The majority of incidents are Medium and Low priority, which is good for system stability.

You: exit
Goodbye!
```

---

## Next Steps & Enhancements

1. Add more sophisticated chunking strategies
2. Implement incident prediction based on trends
3. Add real-time incident ingestion
4. Create custom incident categorization rules
5. Add alerting for anomalous incident patterns
6. Integrate with incident management systems (PagerDuty, etc.)

---

End of Documentation
