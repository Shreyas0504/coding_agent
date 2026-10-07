import re
from collections import Counter

import numpy as np

from tools import list_files, read_file


def _split_code_into_chunks(code, chunk_size=250):
    lines = code.splitlines()
    chunks = []
    current = []
    current_length = 0

    for line in lines:
        current.append(line)
        current_length += len(line)
        if current_length >= chunk_size:
            chunks.append("\n".join(current))
            current = []
            current_length = 0

    if current:
        chunks.append("\n".join(current))

    return chunks or [code]


def _tokenize(text):
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text.lower())


def retrieve_relevant_code(task, top_k=5, file_paths=None):
    results = []

    if file_paths is None:
        file_paths = list_files()
    if not file_paths:
        raise FileNotFoundError("sample_project folder was not found.")

    available_files = set(list_files())
    for file_path in file_paths:
        if file_path not in available_files:
            raise ValueError(f"RAG received a file outside sample_project: {file_path}")

        code = read_file(file_path)
        for chunk in _split_code_into_chunks(code):
            results.append({
                "file_path": file_path,
                "code_chunk": chunk,
                "similarity": 0.0,
            })

    if not results:
        return []

    vocabulary = sorted({
        token
        for item in results
        for token in _tokenize(item["code_chunk"] + " " + item["file_path"])
    })
    vocab_index = {token: index for index, token in enumerate(vocabulary)}

    def build_vector(text):
        counts = Counter(_tokenize(text))
        vector = np.zeros(len(vocabulary), dtype=float)
        for token, count in counts.items():
            if token in vocab_index:
                vector[vocab_index[token]] = count
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector, 0.0
        return vector, norm

    task_vector, task_norm = build_vector(task)
    if task_norm == 0:
        return []

    for item in results:
        chunk_vector, chunk_norm = build_vector(
            item["code_chunk"] + " " + item["file_path"]
        )
        if chunk_norm == 0:
            similarity = 0.0
        else:
            similarity = float(np.dot(task_vector, chunk_vector) / (task_norm * chunk_norm))
        item["similarity"] = round(similarity, 4)

    results.sort(key=lambda item: item["similarity"], reverse=True)
    if results[0]["similarity"] == 0:
        return []
    candidates = []
    seen_files = set()
    for item in results:
        if item["file_path"] in seen_files:
            continue
        seen_files.add(item["file_path"])
        candidates.append(item)
        if len(candidates) >= top_k:
            break
    return candidates
