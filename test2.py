import chromadb
from chromadb.utils import embedding_functions
import re

# 1. نستخدم نموذج أفضل للعربي (هينزل أول مرة بس، بعدين هيبقى محفوظ)
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)

# 2. نجهز قاعدة بيانات جديدة (باسم مختلف عشان منخلطش مع التجربة الأولى)
client = chromadb.PersistentClient(path="./my_database_v2")
collection = client.get_or_create_collection(
    name="fatiha_v2",
    embedding_function=embedding_function
)

# 3. نقرأ النص
with open("sources/fatiha.txt", "r", encoding="utf-8") as f:
    text = f.read()

# 4. نقسم النص حسب أرقام الآيات، زي (1) (2) (3)...
parts = re.split(r'(\(\d+\))', text)

chunks = []
current_chunk = ""
for part in parts:
    if re.match(r'\(\d+\)', part):
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        current_chunk = part
    else:
        current_chunk += part
if current_chunk.strip():
    chunks.append(current_chunk.strip())

# لو مفيش تقسيم بالأرقام، نرجع للتقسيم العادي
if len(chunks) <= 1:
    chunk_size = 500
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

print(f"تم تقسيم النص إلى {len(chunks)} جزء")
for i, c in enumerate(chunks):
    print(f"--- جزء {i} ---")
    print(c[:100])
    print()

# 5. نحفظهم
ids = [f"chunk_{i}" for i in range(len(chunks))]
collection.add(documents=chunks, ids=ids)

print("تم حفظ النص في قاعدة البيانات بنجاح!")

# 6. نجرب نسأل نفس السؤال
question = "ما معنى الرحمن الرحيم؟"
results = collection.query(query_texts=[question], n_results=1)

print("\n--- السؤال ---")
print(question)
print("\n--- أقرب جزء من التفسير ---")
print(results["documents"][0][0])