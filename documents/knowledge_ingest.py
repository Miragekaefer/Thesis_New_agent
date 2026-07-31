from pypdf import PdfReader
import os

DOCUMENT_FOLDER = "documents"

all_text = ""

for filename in os.listdir(DOCUMENT_FOLDER):

    if filename.endswith(".pdf"):

        path = os.path.join(DOCUMENT_FOLDER, filename)

        print(f"Reading {filename}")

        reader = PdfReader(path)

        for page in reader.pages:

            text = page.extract_text()

            if text:
                all_text += text + "\n"

print(all_text[:1000])

chunk_size = 1000

chunks = []

for i in range(0, len(all_text), chunk_size):

    chunks.append(all_text[i:i+chunk_size])

print(f"Created {len(chunks)} chunks")

import ollama

response = ollama.embed(
    model="nomic-embed-text",
    input=chunks[0]
)

print(response)

embeddings = []

for chunk in chunks:

    response = ollama.embed(
        model="nomic-embed-text",
        input=chunk
    )

    embeddings.append({
        "text": chunk,
        "embedding": response["embeddings"][0]
    })

print(len(embeddings))

import json

with open("knowledge.json", "w") as f:

    json.dump(embeddings, f)

print("Knowledge saved.")