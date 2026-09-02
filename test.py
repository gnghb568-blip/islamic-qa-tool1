# هذا أول اختبار بسيط لأداتنا
# الهدف: نحط نص تفسير الفاتحة في قاعدة بيانات ذكية، وبعدين نسأل سؤال ونشوف هل هيرد صح

import chromadb

# 1. نجهز قاعدة البيانات (هتتخزن في مجلد جديد اسمه "my_database")
client = chromadb.PersistentClient(path="./my_database")

# 2. نعمل "كولكشن" (يعني مجلد داخلي) اسمه fatiha
collection = client.get_or_create_collection(name="fatiha")

# 3. نقرأ نص الفاتحة من الملف
with open("sources/fatiha.txt", "r", encoding="utf-8") as f:
    text = f.read()

# 4. نقسم النص لأجزاء صغيرة (كل جزء تقريبًا 500 حرف)
chunk_size = 500
chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

print(f"تم تقسيم النص إلى {len(chunks)} جزء")

# 5. نحط كل جزء في قاعدة البيانات
ids = [f"chunk_{i}" for i in range(len(chunks))]
collection.add(documents=chunks, ids=ids)

print("تم حفظ النص في قاعدة البيانات بنجاح!")

# 6. نجرب نسأل سؤال
question = "ما معنى الرحمن الرحيم؟"
results = collection.query(query_texts=[question], n_results=1)

print("\n--- السؤال ---")
print(question)
print("\n--- أقرب جزء من التفسير ---")
print(results["documents"][0][0])