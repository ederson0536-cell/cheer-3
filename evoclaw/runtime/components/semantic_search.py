"""
Simple Semantic Matching using TF-IDF (no external embedding models needed)
"""
import re
from collections import Counter
import math

from evoclaw.workspace_resolver import resolve_workspace
from evoclaw.sqlite_memory import SQLiteMemoryStore

WORKSPACE = resolve_workspace(__file__)
MEMORY_DB = WORKSPACE / "memory" / "memory.db"

def tokenize(text):
    """Simple Chinese/English tokenization"""
    if not text:
        return []
    # For Chinese, use 2-grams for better matching
    chinese = re.findall(r'[\u4e00-\u9fff]+', text)
    chinese_grams = []
    for word in chinese:
        if len(word) >= 2:
            for i in range(len(word) - 1):
                chinese_grams.append(word[i:i+2])
    english_words = re.findall(r'[a-zA-Z]+', text.lower())
    return chinese_grams + english_words

def compute_tf(tokens):
    """Term frequency"""
    total = len(tokens)
    if total == 0:
        return {}
    counter = Counter(tokens)
    return {word: count/total for word, count in counter.items()}

def compute_idf(documents):
    """Inverse document frequency"""
    N = len(documents)
    idf = {}
    all_words = set()
    for doc in documents:
        all_words.update(doc.keys())
    
    for word in all_words:
        df = sum(1 for doc in documents if word in doc)
        idf[word] = math.log(N / (1 + df)) + 1
    
    return idf

def compute_tfidf(doc, idf):
    """Compute TF-IDF vector"""
    tf = compute_tf(doc)
    return {word: tf_val * idf.get(word, 0) for word, tf_val in tf.items()}

def cosine_similarity(vec1, vec2):
    """Cosine similarity between two vectors"""
    common = set(vec1.keys()) & set(vec2.keys())
    if not common:
        return 0
    
    dot_product = sum(vec1[w] * vec2[w] for w in common)
    mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
    mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
    
    if mag1 == 0 or mag2 == 0:
        return 0
    
    return dot_product / (mag1 * mag2)

def load_experiences(limit=5000):
    """Load experiences from canonical SQLite memory store."""
    store = SQLiteMemoryStore(MEMORY_DB)
    store.init_schema()
    rows = store.query_experiences(limit=limit)

    experiences = []
    for row in rows:
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        exp = {
            "id": row.get("id"),
            "type": row.get("type"),
            "source": row.get("source"),
            "content": row.get("content"),
            "significance": row.get("significance"),
            "timestamp": row.get("created_at"),
        }
        # keep backward-compatible fields when present
        for k in ("summary", "title", "message", "tags"):
            if k in raw and raw.get(k) is not None:
                exp[k] = raw.get(k)
        experiences.append(exp)

    return experiences

def search_similar(query, top_k=5):
    """Find similar experiences using TF-IDF"""
    experiences = load_experiences()
    if not experiences:
        return []
    
    # Tokenize query
    query_tokens = tokenize(query)
    query_doc = compute_tf(query_tokens)
    
    # Build TF-IDF for all experiences
    documents = []
    for exp in experiences:
        # Try different fields
        text = (exp.get('content') or 
                exp.get('message') or 
                exp.get('title') or 
                exp.get('summary') or 
                exp.get('text') or 
                "")
        tokens = tokenize(text)
        documents.append(compute_tf(tokens))
    
    if not documents:
        return []
    
    # Compute IDF
    idf = compute_idf(documents)
    
    # Compute query vector
    query_tfidf = compute_tfidf(query_doc, idf)
    
    # Compute similarities
    similarities = []
    for i, exp in enumerate(experiences):
        doc_tfidf = compute_tfidf(documents[i], idf)
        sim = cosine_similarity(query_tfidf, doc_tfidf)
        if sim > 0.05:  # Lower threshold
            similarities.append((exp, sim))
    
    # Sort by similarity
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    return similarities[:top_k]

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        results = search_similar(query)
        for exp, sim in results:
            text = exp.get('content') or exp.get('message') or exp.get('title') or exp.get('summary') or ""
            print(f"[{sim:.2f}] {text[:100]}")
