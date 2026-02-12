import json
import os
import chromadb
from chromadb.utils import embedding_functions

# --- AYARLAR ---
INPUT_FILENAME = 'AIDADATA.jsonl'
DB_DIRECTORY = 'my_local_vectordb'
COLLECTION_NAME = 'aida_knowledge_base'
BATCH_SIZE = 100 
MODEL_NAME = "all-MiniLM-L6-v2"

def create_local_vector_db():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(current_dir, INPUT_FILENAME)
    db_path = os.path.join(current_dir, DB_DIRECTORY)

    if not os.path.exists(input_path):
        print(f"HATA: '{INPUT_FILENAME}' dosyasi bulunamadi! Once jsonl dosyasini olusturun.")
        return

    print("1. Vektör Veritabani (ChromaDB) hazirlaniyor...")
    print(f"   Model: {MODEL_NAME} (Lokal)")
    print(f"   Veritabani Yolu: {db_path}")

    # 1. ChromaDB İstemcisini Başlat
    client = chromadb.PersistentClient(path=db_path)

    # 2. Embedding Fonksiyonu
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME
    )

    # 3. Koleksiyon Oluşturma
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"   Eski koleksiyon '{COLLECTION_NAME}' silindi (Temiz kurulum).")
    except Exception as e:
        print(f"   Yeni koleksiyon olusturuluyor...")

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"}
    )

    print("2. Veriler okunuyor ve veritabanina yukleniyor...")
    
    documents = []
    metadatas = []
    ids = []
    
    # ID Takibi için sözlük (Hangi ID kaç kere görüldü?)
    seen_ids = {}
    
    count = 0
    total_added = 0

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    
                    doc_text = record.get('text_for_embedding', '')
                    raw_id = str(record.get('id'))
                    
                    if not raw_id or not doc_text:
                        continue

                    # --- ID CAKISMASI COZUMU ---
                    # Eğer ID daha önce görüldüyse sonuna _1, _2 ekle
                    if raw_id in seen_ids:
                        seen_ids[raw_id] += 1
                        unique_id = f"{raw_id}_{seen_ids[raw_id]}" # Örn: 2207973703_1
                    else:
                        seen_ids[raw_id] = 0
                        unique_id = raw_id
                    # ---------------------------

                    meta = {
                        "business_key": record.get('business_key', 'N/A'),
                        "state": record.get('state', 'N/A'),
                        "ticket": record.get('ticket', 'N/A'),
                        "function_id": str(record.get('function_id', 'N/A')),
                        "original_id": raw_id # Orijinal ID'yi metadata'da saklayalım
                    }

                    documents.append(doc_text)
                    metadatas.append(meta)
                    ids.append(unique_id) # Benzersiz ID'yi kullan
                    count += 1

                    if count >= BATCH_SIZE:
                        collection.add(
                            documents=documents,
                            metadatas=metadatas,
                            ids=ids
                        )
                        total_added += len(ids)
                        print(f"   {total_added} kayit islendi...", end='\r')
                        
                        documents = []
                        metadatas = []
                        ids = []
                        count = 0

                except json.JSONDecodeError:
                    continue
        
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            total_added += len(ids)

    except Exception as e:
        print(f"\nBir hata olustu: {e}")
        # Hata olsa bile şimdiye kadar eklenenleri kaydeder
        
    print(f"\n\nIslem Tamamlandi! Toplam {total_added} kayit vektör veritabanina eklendi.")
    print(f"Duplicate ID'ler '_1', '_2' seklinde isimlendirilerek kaydedildi.")
    print(f"Veritabani su klasorde saklaniyor: {db_path}")

    # --- TEST ---
    print("\n--- TEST SORGUSU ---")
    try:
        results = collection.query(
            query_texts=["arabanin ön kapagini acmak"],
            n_results=1
        )
        if results['documents'] and len(results['documents'][0]) > 0:
            print("Bulunan Sonuç:")
            print(results['documents'][0][0])
            print("Metadata:")
            print(results['metadatas'][0][0])
        else:
            print("Sonuç bulunamadı.")
    except Exception as e:
        print(f"Test sorgusu sirasinda hata: {e}")

if __name__ == "__main__":
    create_local_vector_db()