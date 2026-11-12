"""Mini exercise 2: Chroma basics + distance scores (needed for the evidence cutoff)."""
import chromadb

client = chromadb.Client()
col = client.create_collection("demo")
col.add(ids=["a", "b", "c", "d", "e"], documents=[
    "Rising vibration on a centrifugal pump usually indicates bearing wear.",
    "High discharge temperature can come from a blocked heat exchanger.",
    "A slow pressure drop may indicate a leaking mechanical seal.",
    "Replace the air filter on the compressor every 2000 hours.",
    "Motor current rising with constant load suggests winding degradation.",
])
for q in ["pump shaking more than usual", "stock market crash", "seal leak"]:
    r = col.query(query_texts=[q], n_results=2)
    print(q, "->", list(zip(r["ids"][0], [round(d, 2) for d in r["distances"][0]])))
# TODO: note the distance for the nonsense query. That gap is your 'no reliable evidence' cutoff.
