# 🛒 E-Mall SASRec — AI Recommendation System

## مشروع التخرج — GP-02
**نظام توصيات ذكي مبني على نموذج SASRec (Self-Attentive Sequential Recommendation)**

---

## 📌 نظرة عامة / Overview

This project implements a complete **AI-powered product recommendation pipeline** for the E-Mall e-commerce platform. It uses the **SASRec** model — a Transformer-based sequential recommendation architecture — to predict the next products a user is likely to interact with based on their browsing/purchase history.

> هذا المشروع يبني نظام توصيات ذكي لمنصة E-Mall باستخدام نموذج SASRec المبني على Transformer. النظام يتنبأ بالمنتجات اللي المستخدم ممكن يتفاعل معها بناءً على تاريخ تصفحه ومشترياته.

---

## 📁 هيكلية المشروع / Project Structure

```
GP - Dataset/
├── sasrec_emall.ipynb          # 📓 Notebook الرئيسي (Colab ready)
├── interactions.csv            # 📊 بيانات التفاعلات (961k+ سجل)
├── products.csv                # 🏷️  بيانات المنتجات
├── users.csv                   # 👥 بيانات المستخدمين
├── categories.csv              # 📂 التصنيفات
├── product_mappings.csv        # 🔗 ربط المنتجات بالفهارس
├── data_summary.txt            # 📝 ملخص البيانات
├── figures/                    # 📈 الرسومات البيانية (تُنشأ تلقائياً)
├── README.md                   # 📖 هذا الملف
│
└── api/                        # 🌐 FastAPI Recommendation Service
    ├── __init__.py              # Package marker
    ├── config.py                # ⚙️  إعدادات المسارات والمعاملات
    ├── model.py                 # 🧠 بنية نموذج SASRec
    ├── schemas.py               # 📋 Pydantic request/response models
    ├── main.py                  # 🚀 FastAPI endpoints
    ├── train_and_save.py        # 🏋️  سكربت التدريب المستقل
    ├── requirements.txt         # 📦 المكتبات المطلوبة
    └── checkpoints/
        └── sasrec_emall.pth     # 💾 ملف الموديل المُدرَّب
```

---

## 🧠 شرح نموذج SASRec / Model Architecture

SASRec (Self-Attentive Sequential Recommendation) هو نموذج توصيات قائم على **Transformer** بتصميم أحادي الاتجاه (causal/unidirectional):

```
مدخل التسلسل → Item Embedding + Position Embedding → [SASRec Block] × N → Hidden state → Dot-product Score
```

### مكونات كل SASRec Block:
1. **LayerNorm → Multi-Head Self-Attention (causal)** — يتعلم العلاقات بين المنتجات في التسلسل
2. **LayerNorm → Point-Wise Feed-Forward (Conv1d)** — يعالج كل موقع بشكل مستقل
3. **Residual Connections** — تسهل تدريب الشبكة العميقة

### المعاملات الفائقة (Hyperparameters):

| المعامل | القيمة | الوصف |
|---------|--------|-------|
| `hidden_dim` | 64 | بُعد الـ embedding لكل عنصر |
| `num_blocks` | 2 | عدد طبقات Transformer |
| `num_heads` | 1 | عدد رؤوس الانتباه |
| `max_seq_len` | 50 | أقصى طول للتسلسل |
| `dropout_rate` | 0.2 | نسبة التسريب |
| `learning_rate` | 0.001 | معدل التعلم |
| `batch_size` | 256 | حجم الدفعة |

---

## 📊 البيانات / Dataset

### interactions.csv

| العمود | النوع | الوصف |
|--------|-------|-------|
| `interaction_id` | int | معرف فريد للتفاعل |
| `user_id` | int | معرف المستخدم |
| `product_id` | int | معرف المنتج |
| `interaction_type` | str | نوع التفاعل: `view`, `click`, `add_to_cart`, `purchase` |
| `timestamp` | datetime | وقت التفاعل |

- **عدد التفاعلات**: ~961,370 سجل
- **المستخدمين**: عدة آلاف
- **المنتجات**: ~1,000 منتج

### استراتيجية تقسيم البيانات (Leave-One-Out):

| المجموعة | البيانات المستخدمة |
|----------|-------------------|
| **Train** | كل العناصر ما عدا آخر 2 |
| **Validation** | العنصر قبل الأخير |
| **Test** | العنصر الأخير |

---

## 📓 شرح الـ Notebook بالتفصيل / Notebook Walkthrough

### Cell 0 — 🔗 Google Drive Mount
```python
from google.colab import drive
drive.mount('/content/drive')
DRIVE_SUBFOLDER = ""   # خلي فاضي إذا الملفات بجذر الـ Drive
```
- يربط Google Drive مع Colab
- **`DRIVE_SUBFOLDER`**: اتركه فاضي `""` إذا ملفات المشروع موجودة مباشرة في `My Drive`، أو حط المسار مثلاً `"GP - Dataset"`

### Cell 1 — Setup & Imports
- استيراد المكتبات: `torch`, `numpy`, `pandas`, `matplotlib`, `seaborn`
- ضبط الـ seed لنتائج قابلة للتكرار
- تكوين مجلد `figures/` داخل المشروع في Drive

### Cell 2 — Data Preprocessing
- تحميل `interactions.csv` من Drive
- ترتيب البيانات زمنياً لكل مستخدم
- بناء `item2idx` و `idx2item` (ربط المنتجات بأرقام)
- تقسيم البيانات: Train / Val / Test

### Cell 3 — SASRec Architecture
- تعريف ثلاث فئات:
  - **`PointWiseFeedForward`** — شبكة FFN باستخدام Conv1d
  - **`SASRecBlock`** — بلوك Transformer كامل
  - **`SASRec`** — النموذج الرئيسي

### Cell 4 — Dataset & DataLoader
- **`SASRecDataset`** — يُنتج عينات تدريب مع negative sampling
- DataLoader بحجم batch = 256

### Cell 5 — Training Loop
- تدريب لمدة 10 epochs
- BCE Loss مع masking للـ padding
- Gradient clipping (max_norm=5.0)
- حساب Val HR@10 و NDCG@10 بعد كل epoch

### Cell 6 — ✅ Results Display
- عرض منظم لـ:
  - سجل التدريب (loss لكل epoch)
  - مقاييس Validation النهائية
  - مقاييس Test
  - أفضل 5 توصيات لمستخدم محدد

### Cell 7 — 📊 Visualizations
- **4 رسومات بيانية** محفوظة في `figures/`:
  1. `01_training_loss.png` — منحنى الخسارة
  2. `02_eval_metrics.png` — HR@10 و NDCG@10
  3. `03_model_architecture.png` — تفاصيل معمارية النموذج
  4. `04_attention_heatmap.png` — خريطة حرارية للانتباه

### Cell 8 — 🔍 Inference
- تجربة التوصيات على مجموعة مستخدمين (1, 2, 3)
- عرض Top-5 توصيات لكل مستخدم

### Cell 9 — 💾 Model Export & Reload
- حفظ checkpoint يتضمن:
  - أوزان النموذج (`model_state_dict`)
  - خرائط العناصر (`item2idx`, `idx2item`)
  - تسلسلات المستخدمين (`user_sequences`)
  - المعاملات (`hyperparams`)
  - المقاييس (`metrics`)
- اختبار إعادة التحميل والاستنتاج

### Cell 10 — 🌐 API Server
- تثبيت FastAPI + uvicorn + pyngrok
- إنشاء ملف API ذاتي وتشغيله
- فتح نفق ngrok للوصول من Postman

---

## 🌐 شرح الـ API / API Documentation

### تشغيل الـ API محلياً (Local — Postman Testing)

```bash
# 1. تثبيت المكتبات
cd "GP - Dataset"
pip install -r api/requirements.txt

# 2. تدريب النموذج (مرة واحدة فقط)
python api/train_and_save.py

# 3. تشغيل السيرفر
uvicorn api.main:app --reload --port 8000
```

### Endpoints

#### `GET /health` — فحص حالة السيرفر
```json
// Response
{
  "status": "ok",
  "model_loaded": true,
  "num_items": 999,
  "num_users": 30000,
  "device": "cpu",
  "model_version": "1.0.0"
}
```

#### `POST /recommend` — توصيات لمستخدم واحد
```json
// Request Body
{
  "user_id": 1,
  "top_k": 5,
  "exclude_interacted": true
}

// Response
{
  "user_id": 1,
  "recommendations": [
    { "rank": 1, "product_id": 321, "score": 2.4567 },
    { "rank": 2, "product_id": 705, "score": 2.3012 },
    ...
  ],
  "model_version": "1.0.0"
}
```

#### `POST /recommend/batch` — توصيات لعدة مستخدمين
```json
// Request Body
{
  "user_ids": [1, 42, 100],
  "top_k": 5,
  "exclude_interacted": true
}
```

#### `POST /recommend/sequence` — توصيات من تسلسل منتجات
```json
// Request Body
{
  "product_ids": [321, 705, 14],
  "top_k": 5,
  "exclude_input": true
}
```
> مفيد للمستخدمين المجهولين (anonymous users) أو جلسات التصفح

#### `POST /recommend/similar` — منتجات مشابهة
```json
// Request Body
{
  "product_id": 321,
  "top_k": 5
}

// Response
{
  "product_id": 321,
  "similar_items": [
    { "rank": 1, "product_id": 450, "score": 0.9234 },
    ...
  ],
  "model_version": "1.0.0"
}
```
> يستخدم cosine similarity بين item embeddings

### Swagger UI
بعد تشغيل السيرفر، افتح في المتصفح:
- **Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🗂️ شرح ملفات الـ API / API Files Explained

### `config.py`
إعدادات مركزية:
- مسارات الملفات (checkpoint, data CSVs)
- المعاملات الفائقة (يجب أن تتطابق مع التدريب)
- إعدادات CORS
- معلومات API (title, version, description)

### `model.py`
تعريف بنية SASRec بنسخة نظيفة:
- `PointWiseFeedForward` — FFN بـ Conv1d
- `SASRecBlock` — Self-Attention + FFN + LayerNorm
- `SASRec` — النموذج الكامل مع `predict()`

### `schemas.py`
Pydantic models لضمان صحة البيانات:
- **Request**: `RecommendRequest`, `BatchRecommendRequest`, `SequenceRecommendRequest`, `SimilarItemsRequest`
- **Response**: `RecommendResponse`, `RecommendedProduct`, `HealthResponse`, `ErrorResponse`

### `main.py`
FastAPI application:
- `ModelState` class — يحمل النموذج والبيانات
- Lifespan — يحمل النموذج عند بدء السيرفر
- 5 endpoints مع توثيق تلقائي

### `train_and_save.py`
سكربت تدريب مستقل:
- يُفلتر التفاعلات القوية (purchase + add_to_cart)
- Early stopping (patience=20)
- يحفظ checkpoint يتضمن كل شيء للاستنتاج

---

## 🔄 سير العمل الكامل / Full Workflow

### خيار 1: Google Colab (مُوصى به)

```
1. ارفع ملفات المشروع على Google Drive
2. افتح sasrec_emall.ipynb في Colab
3. اضبط DRIVE_SUBFOLDER حسب مكان الملفات
4. شغّل كل الخلايا بالترتيب
5. الخلية الأخيرة تشغل API server مع ngrok
6. استخدم الرابط في Postman
```

### خيار 2: محلي (Local)

```
1. pip install -r api/requirements.txt
2. python api/train_and_save.py      # مرة واحدة
3. uvicorn api.main:app --reload --port 8000
4. افتح Postman واستخدم http://localhost:8000
```

---

## 📎 ملاحظات مهمة / Important Notes

- **الـ Checkpoint** اسمه `sasrec_emall.pth` — نفس الاسم في الـ notebook وفي `config.py`
- **`DRIVE_SUBFOLDER`** في أول خلية بالـ notebook — خليها فاضية `""` إذا الملفات على جذر Drive
- **الـ API بتشتغل محلياً** بدون Drive — فقط تأكد إنو ملف `sasrec_emall.pth` موجود في `api/checkpoints/`
- **مقاييس التقييم**:
  - **HR@10** (Hit Rate) — هل المنتج الصحيح ضمن أفضل 10 توصيات؟
  - **NDCG@10** (Normalized Discounted Cumulative Gain) — جودة الترتيب
- كل الرسومات البيانية تُحفظ تلقائياً في مجلد `figures/`

---

## 🛠️ المكتبات المطلوبة / Dependencies

| المكتبة | الاستخدام |
|---------|----------|
| `torch` ≥ 2.0 | بناء وتدريب النموذج |
| `pandas` ≥ 2.0 | معالجة البيانات |
| `numpy` ≥ 1.24 | عمليات رقمية |
| `matplotlib` | رسومات بيانية |
| `seaborn` | خرائط حرارية |
| `fastapi` ≥ 0.115 | بناء الـ API |
| `uvicorn` ≥ 0.30 | تشغيل الـ API |
| `pydantic` ≥ 2.0 | التحقق من صحة البيانات |
| `pyngrok` | (Colab فقط) نفق ngrok |

---

## 📚 المراجع / References

- **SASRec Paper**: Kang & McAuley, *"Self-Attentive Sequential Recommendation"* (ICDM 2018)
- **PyTorch**: https://pytorch.org/
- **FastAPI**: https://fastapi.tiangolo.com/

---

> **GP-02 — E-Mall Smart E-Commerce Platform** 🎓
