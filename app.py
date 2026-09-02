from flask import Flask, render_template, request, session, Response, stream_with_context
import chromadb
from chromadb.utils import embedding_functions
import os
import json
import requests
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3.5-flash-lite")

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

TRUSTED_SITES = [
    "islamweb.net", "dar-alifta.org", "islamqa.info", "binbaz.org.sa",
    "alifta.gov.sa", "dorar.net", "islamway.net", "alukah.net",
    "azhar.eg", "aljam3.com", "islamhouse.com", "al-eman.com",
    "saaid.net", "sunnah.com", "ahlalhdeeth.com", "ibn-jebreen.com",
    "binothaimeen.net", "shamela.ws", "al-feqh.com", "islamonline.net",
    "rasoulallah.net", "islamweb.org", "dorar-hadith.net", "islamport.com",
    "islamage.com", "kalemtayeb.com", "al-ifta.com", "islamqa.org",
    "tafsir.app", "islamsyria.com"
]

app = Flask(__name__)
app.secret_key = "islamic-qa-secret-key-change-later"
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30  # الجلسة تفضل شغالة 30 يوم

embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)
client = chromadb.PersistentClient(path="./my_database_v2")
collection = client.get_or_create_collection(
    name="fatiha_v2",
    embedding_function=embedding_function
)

executor = ThreadPoolExecutor(max_workers=4)

# كاش بسيط: بيحفظ آخر 200 سؤال وإجابته عشان ميكررش نفس الطلب لـ Gemini والبحث
answer_cache = {}
CACHE_MAX_SIZE = 200


def get_cached_answer(question):
    key = question.strip().lower()
    return answer_cache.get(key)


def save_to_cache(question, answer):
    key = question.strip().lower()
    if len(answer_cache) >= CACHE_MAX_SIZE:
        # نشيل أقدم عنصر لما الكاش يمتلئ
        oldest_key = next(iter(answer_cache))
        del answer_cache[oldest_key]
    answer_cache[key] = answer


def search_local(query):
    results = collection.query(query_texts=[query], n_results=1)
    return results["documents"][0][0]


def search_trusted_sites(query):
    site_filter = " OR ".join([f"site:{s}" for s in TRUSTED_SITES[:10]])
    full_query = f"{query} ({site_filter})"

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": full_query, "gl": "eg", "hl": "ar", "num": 2}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=8)
        data = response.json()
        results = []
        for item in data.get("organic", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", "")
            })
        return results
    except Exception as e:
        print("خطأ في البحث:", e)
        return []


def stream_gemini(prompt):
    full_answer = ""
    response = model.generate_content(prompt, stream=True)
    for chunk in response:
        if chunk.text:
            full_answer += chunk.text
            yield chunk.text
    return full_answer


@app.route("/")
def home():
    session.permanent = True
    if "chat_history" not in session:
        session["chat_history"] = []
    return render_template("index.html", chat_history=session.get("chat_history", []))


@app.route("/ask", methods=["POST"])
def ask():
    session.permanent = True
    question = request.json.get("question", "")
    history_snapshot = session.get("chat_history", [])
    awaiting_answer = session.get("awaiting_story_answer", False)
    story_context = session.get("story_context", "")

    def generate():
        if awaiting_answer:
            prompt = f"""أنت معلم إسلامي لطيف. كنت قد رويت القصة التالية وسألت سؤالاً عنها:

القصة والسؤال:
{story_context}

إجابة المستخدم: {question}

قيّم إجابة المستخدم بلطف: إن كانت صحيحة، امدحه بإيجاز واذكر لماذا هي صحيحة. إن كانت خاطئة أو ناقصة، صحح له بأسلوب تربوي مشجع مع ذكر الإجابة الصحيحة. اجعل ردك مختصراً."""
            session["awaiting_story_answer"] = False
            session["story_context"] = ""
        else:
            # نتأكد الأول هل السؤال ده اتسأل قبل كده (كاش)
            cached = get_cached_answer(question)
            if cached:
                yield f"data: {json.dumps({'chunk': cached, 'cached': True})}\n\n"
                history_snapshot.append({"role": "user", "text": question})
                history_snapshot.append({"role": "bot", "text": cached})
                session["chat_history"] = history_snapshot
                session.modified = True
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            yield f"data: {json.dumps({'status': 'searching'})}\n\n"

            future_local = executor.submit(search_local, question)
            future_web = executor.submit(search_trusted_sites, question)
            local_text = future_local.result()
            web_results = future_web.result()

            web_text = ""
            for r in web_results:
                web_text += f"\n- من {r['link']}:\n{r['snippet']}\n"

            prompt = f"""أنت مساعد إسلامي. أجب على السؤال التالي بالاعتماد على المصادر المرجعية أدناه فقط.

السؤال: {question}

المصدر المحلي (تفسير السعدي - سورة الفاتحة):
{local_text}

نتائج بحث من مواقع إسلامية موثوقة:
{web_text if web_text else "لا توجد نتائج بحث متاحة."}

اكتب إجابة طبيعية وواضحة ومختصرة بناءً على المصادر أعلاه فقط. إن وجدت المعلومة في نتائج البحث، اذكر اسم الموقع المصدر في نهاية الإجابة. إن لم تكن المصادر كافية للإجابة، وضح ذلك بأمانة."""

        full_answer = ""
        for piece in stream_gemini(prompt):
            full_answer += piece
            yield f"data: {json.dumps({'chunk': piece})}\n\n"

        # نحفظ في الكاش بس لو كان سؤال عادي (مش رد على قصة)
        if not awaiting_answer:
            save_to_cache(question, full_answer)

        history_snapshot.append({"role": "user", "text": question})
        history_snapshot.append({"role": "bot", "text": full_answer})
        session["chat_history"] = history_snapshot
        session.modified = True

        yield f"data: {json.dumps({'done': True})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/story", methods=["POST"])
def story():
    session.permanent = True
    history_snapshot = session.get("chat_history", [])
    topic = request.json.get("topic", "عام")

    topic_instructions = {
        "أنبياء": "من قصص الأنبياء عليهم السلام",
        "صحابة": "من قصص الصحابة رضي الله عنهم",
        "سيرة": "من السيرة النبوية الشريفة",
        "عام": "من السيرة النبوية أو قصص الصحابة أو الأنبياء"
    }
    chosen = topic_instructions.get(topic, topic_instructions["عام"])

    prompt = f"""أنت راوي قصص إسلامي ماهر. اروِ قصة قصيرة (فقرة أو فقرتين) {chosen}، بأسلوب شيق ومناسب لجميع الأعمار، معتمداً على الروايات الصحيحة المعروفة فقط.

في نهاية القصة، اطرح سؤالاً واحداً بسيطاً عن تفاصيل القصة (مثل: اسم شخصية، أو حدث معين، أو درس مستفاد).

اكتب القصة والسؤال في نص واحد متصل بدون عناوين إضافية."""

    def generate():
        full_story = ""
        for piece in stream_gemini(prompt):
            full_story += piece
            yield f"data: {json.dumps({'chunk': piece})}\n\n"

        session["story_context"] = full_story
        session["awaiting_story_answer"] = True

        history_snapshot.append({"role": "bot", "text": full_story})
        session["chat_history"] = history_snapshot
        session.modified = True

        yield f"data: {json.dumps({'done': True})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/clear")
def clear():
    session.permanent = True
    session["chat_history"] = []
    session["awaiting_story_answer"] = False
    session["story_context"] = ""
    return render_template("index.html", chat_history=[])


if __name__ == "__main__":
    app.run(debug=True, threaded=True)