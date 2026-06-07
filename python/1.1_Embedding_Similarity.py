# Goal: Understand how vector similarity works
import re

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:
    SentenceTransformer = None


text1 = "Database connection failed"
text2 = "Unable to connect to the database"
text3 = "Data analysis is important for business decisions"


def simple_bow_embeddings(texts):
    # Fallback embedding: bag-of-words term frequency vectors.
    tokenized = [re.findall(r"\w+", text.lower()) for text in texts]
    vocabulary = sorted({token for tokens in tokenized for token in tokens})
    index = {token: i for i, token in enumerate(vocabulary)}

    vectors = np.zeros((len(texts), len(vocabulary)), dtype=float)
    for row, tokens in enumerate(tokenized):
        for token in tokens:
            vectors[row, index[token]] += 1.0

    return vectors


if SentenceTransformer is not None:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embedding1 = model.encode(text1)
    embedding2 = model.encode(text2)
    embedding3 = model.encode(text3)
else:
    print(
        "sentence_transformers not installed. "
        "Using bag-of-words fallback embeddings."
    )
    embedding1, embedding2, embedding3 = simple_bow_embeddings([text1, text2, text3])

def cosine_similarity(vec1, vec2):
    dot_product = np.dot(vec1, vec2)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)
    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0
    return dot_product / (norm_vec1 * norm_vec2)

similarity_1_2 = cosine_similarity(embedding1, embedding2)
similarity_1_3 = cosine_similarity(embedding1, embedding3)

print(f"Similarity between Text 1 and Text 2: {similarity_1_2:.4f}")
print(f"Similarity between Text 1 and Text 3: {similarity_1_3:.4f}")