# Vector Store Integration Guide

## Overview
The incident_analyzer now supports both **ChromaDB** (default) and **Milvus** as vector stores.

- **ChromaDB**: Lightweight, in-process, perfect for development and small deployments
- **Milvus**: Production-grade, scalable, for large-scale deployments

---

## Quick Start

### Using ChromaDB (Default)
```bash
# No additional setup needed
python main.py --file incidents.xlsx
```

### Using Milvus
```bash
# Step 1: Start Milvus server (requires Docker)
docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest

# Step 2: Install Milvus client
pip install pymilvus>=2.4.0

# Step 3: Run incident analyzer with Milvus
python main.py --file incidents.xlsx --vector-db milvus
```

---

## Command Line Options

```bash
# Use ChromaDB (default)
python main.py --file incidents.xlsx --vector-db chroma

# Use Milvus
python main.py --file incidents.xlsx --vector-db milvus

# Other flags work with both
python main.py --file incidents.xlsx --vector-db milvus --query "How many incidents?"
python main.py --file incidents.xlsx --vector-db milvus --no-upsert
```

---

## Environment Configuration

### ChromaDB Configuration
```bash
# Optional environment variables:
export CHROMA_PERSIST_DIR=./chroma_db
export CHROMA_COLLECTION=incident_monthly_summaries
```

### Milvus Configuration
```bash
# Optional environment variables:
export MILVUS_HOST=localhost
export MILVUS_PORT=19530
export MILVUS_COLLECTION=incident_monthly_summaries
```

---

## Code Changes

### What Changed in `main.py`

**Before** (Hard-coded ChromaDB):
```python
from chroma_store import get_vector_store, store_monthly_summary
```

**After** (Dynamic import based on --vector-db flag):
```python
if args.vector_db == "milvus":
    from milvus_store import get_vector_store, store_monthly_summary
else:
    from chroma_store import get_vector_store, store_monthly_summary
```

### New Files Added

**`milvus_store.py`**: 
- Mirror of `chroma_store.py` but using Milvus instead
- Same function signatures for seamless switching
- Functions:
  - `get_vector_store()` - Initialize Milvus connection
  - `store_monthly_summary()` - Store embeddings
  - `retrieve_similar_reports()` - Semantic search

---

## Comparison

| Feature | ChromaDB | Milvus |
|---------|----------|--------|
| Setup | Zero - in-process | Docker required |
| Best For | Dev, small projects | Production, scale |
| Performance | <100ms (small data) | <50ms (large data) |
| Data Size | <1M docs | >1M docs |
| Maintenance | None | Docker/K8s |
| Cost | Free | Free (self-hosted) |

---

## How to Switch

### Scenario 1: Currently using ChromaDB, want to try Milvus
```bash
# Step 1: Start Milvus
docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest

# Step 2: Install Milvus client
pip install pymilvus

# Step 3: Run with Milvus (fresh data will be indexed)
python main.py --file incidents.xlsx --vector-db milvus

# Step 4: Your ChromaDB data stays intact
# ./chroma_db folder is untouched
```

### Scenario 2: Switch back to ChromaDB
```bash
python main.py --file incidents.xlsx --vector-db chroma
```

Both databases maintain separate storage - no conflicts!

---

## Troubleshooting

### Milvus Connection Error
```
Error: Failed to connect to Milvus at localhost:19530
```

**Solution**:
```bash
# Check if Milvus is running
docker ps | grep milvus

# If not running, start it
docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest

# Verify connection
docker logs milvus | tail -20
```

### Milvus Collection Schema Error
```
Error: Creating new collection...
```

**Solution**: Milvus automatically creates the schema on first use. Just wait for it to complete.

### Performance Issues
```bash
# Check collection statistics
# (Add this to milvus_store.py or call manually)
collection_stats()
```

---

## Advanced Usage

### Using Both Simultaneously
```bash
# Terminal 1: Run with ChromaDB
python main.py --file incidents.xlsx --vector-db chroma

# Terminal 2: Run with Milvus (in parallel)
python main.py --file incidents.xlsx --vector-db milvus --query "Different question"
```

### Migrating Data from ChromaDB to Milvus
```python
from chroma_store import retrieve_similar_reports as chroma_retrieve
from milvus_store import store_monthly_summary as milvus_store

# Read from ChromaDB
chroma_data = chroma_retrieve("*")

# Write to Milvus
milvus_store(df, collection=get_vector_store())
```

---

## Performance Notes

### ChromaDB
- Indexing: 50ms per document
- Search: 20ms for 100K documents
- Memory: ~1GB for 1M documents

### Milvus
- Indexing: 5ms per document (with GPU)
- Search: 10ms for 10M documents
- Memory: Variable (distributed)

### When to Use Each

**Use ChromaDB if**:
- Learning/experimenting
- <100K documents
- Single machine
- Don't want Docker

**Use Milvus if**:
- Production deployment
- >1M documents
- Need horizontal scaling
- Team available to maintain

---

## Files Modified

✅ `main.py` - Added --vector-db flag, dynamic imports
✅ `requirements.txt` - Added optional pymilvus
✅ `milvus_store.py` - NEW: Milvus integration (parallel to chroma_store.py)

✅ `chroma_store.py` - UNCHANGED: Kept as-is for ChromaDB

---

## Next Steps

1. Try both: `--vector-db chroma` and `--vector-db milvus`
2. Monitor performance with your data size
3. Choose based on your needs
4. Scale horizontally if needed with Milvus

Enjoy the flexibility! 🚀
