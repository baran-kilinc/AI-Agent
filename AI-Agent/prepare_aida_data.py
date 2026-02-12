import json
import os

# Dosya adları
INPUT_FILENAME = 'AIDAROHDATA.json'
OUTPUT_FILENAME = 'AIDADATA.jsonl'

def stream_json_objects(file_path):
    """
    Bellek dostu akış okuyucu.
    Dosyayı karakter karakter okur ve bitişik JSON nesnelerini ayırır.
    Bu yöntem {..}{..} şeklindeki bozuk formatları ve GB'lık dosyaları yönetebilir.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        buffer = []
        brace_count = 0
        in_string = False
        escape = False
        started = False
        
        while True:
            # 1MB'lık bloklar halinde oku (bilgisayarı yormamak için)
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            
            for char in chunk:
                # Tırnak içi karakter kontrolü (Parantezleri metin sanmasın diye)
                if in_string:
                    if char == '\\':
                        escape = not escape # Escape karakteri kontrolü
                    elif char == '"' and not escape:
                        in_string = False
                    else:
                        escape = False
                else:
                    if char == '"':
                        in_string = True
                    elif char == '{':
                        brace_count += 1
                        started = True
                    elif char == '}':
                        brace_count -= 1

                buffer.append(char)

                # Bir JSON bloğu tamamlandı mı? (Parantez sayısı 0'a döndüyse)
                if started and brace_count == 0 and not in_string:
                    json_str = "".join(buffer).strip()
                    if json_str:
                        try:
                            # Bulunan parçayı JSON'a çevir ve gönder
                            yield json.loads(json_str)
                        except json.JSONDecodeError:
                            # Arada boşluk veya bozuk karakter varsa pas geç
                            pass
                    
                    # Hafızayı temizle
                    buffer = []
                    started = False

def process_aida_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(current_dir, INPUT_FILENAME)
    output_path = os.path.join(current_dir, OUTPUT_FILENAME)

    print(f"Prozess fängt an...")
    print(f"Quelle: {input_path}")
    print("Daten werden verarbeitet...")

    if not os.path.exists(input_path):
        print(f"HATA: '{INPUT_FILENAME}' dosyasi bulunamadi!")
        return

    processed_count = 0
    skipped_blocks = 0

    try:
        with open(output_path, 'w', encoding='utf-8') as out_f:
            # stream_json_objects fonksiyonundan gelen her parçayı tek tek işle
            for block in stream_json_objects(input_path):
                
                # 'results' kısmını bul
                results = block.get('results', [])
                if isinstance(results, dict): 
                    results = [results]
                
                for res_item in results:
                    items = res_item.get('items', [])
                    
                    # Eğer items boşsa veya yoksa sayacı artır ve devam et
                    if not items or len(items) == 0:
                        skipped_blocks += 1
                        continue

                    # Dolu verileri işle
                    for item in items:
                        name_en = item.get('nameen', '')
                        name_de = item.get('name', '')
                        desc_en = item.get('descriptionen', '')
                        desc_de = item.get('description', '')
                        
                        # Vektör veritabanı için anlamlı metin bloğu
                        embedding_text = (
                            f"Title (EN): {name_en}\n"
                            f"Title (DE): {name_de}\n"
                            f"Description (EN): {desc_en}\n"
                            f"Description (DE): {desc_de}"
                        ).strip()

                        # Sadece ID olan ama içi boş verileri kaydetme
                        if not embedding_text.replace("Title (EN):", "").strip():
                            continue

                        # Kaydedilecek satır
                        record = {
                            "id": str(item.get('id', '')),
                            "business_key": item.get('businesskey', ''),
                            "ticket": item.get('ticketcocojira', ''),
                            "state": item.get('state', 'UNKNOWN'),
                            "function_id": item.get('function_id', ''),
                            "text_for_embedding": embedding_text
                        }

                        # JSON Lines formatında dosyaya yaz
                        out_f.write(json.dumps(record, ensure_ascii=False) + '\n')
                        processed_count += 1
                        
                        # Kullanıcıya ilerlemeyi göster
                        if processed_count % 1000 == 0:
                            print(f"Total Blocks: {processed_count}...", end='\r')

    except Exception as e:
        print(f"\nERROR: {e}")
        return

    print(f"\n\nAbgeschlossen!!")
    print(f"Total gespeicherte Blocks: {processed_count}")
    print(f"Geloeschte Blocks: {skipped_blocks}")
    print(f"Output: {output_path}")

if __name__ == "__main__":
    process_aida_data()