---
base_model: Omartificial-Intelligence-Space/Arabic-Triplet-Matryoshka-V2
datasets:
- Omartificial-Intelligence-Space/Arabic-stsb
- Omartificial-Intelligence-Space/Arabic-NLi-Pair-Class
language:
- ar
library_name: sentence-transformers
license: apache-2.0
metrics:
- pearson_cosine
- spearman_cosine
- pearson_manhattan
- spearman_manhattan
- pearson_euclidean
- spearman_euclidean
- pearson_dot
- spearman_dot
- pearson_max
- spearman_max
pipeline_tag: feature-extraction
tags:
- mteb
- sentence-transformers
- sentence-similarity
- feature-extraction
- generated_from_trainer
- dataset_size:947818
- loss:SoftmaxLoss
- loss:CosineSimilarityLoss
- transformers
widget:
- source_sentence: امرأة تكتب شيئاً
  sentences:
  - مراهق يتحدث إلى فتاة عبر كاميرا الإنترنت
  - امرأة تقطع البصل الأخضر.
  - مجموعة من كبار السن يتظاهرون حول طاولة الطعام.
- source_sentence: تتشكل النجوم في مناطق تكوين النجوم، والتي تنشأ نفسها من السحب الجزيئية.
  sentences:
  - لاعب كرة السلة على وشك تسجيل نقاط لفريقه.
  - المقال التالي مأخوذ من نسختي من "أطلس البطريق الجديد للتاريخ الوسطى"
  - قد يكون من الممكن أن يوجد نظام شمسي مثل نظامنا خارج المجرة
- source_sentence: تحت السماء الزرقاء مع الغيوم البيضاء، يصل طفل لمس مروحة طائرة واقفة
    على حقل من العشب.
  sentences:
  - امرأة تحمل كأساً
  - طفل يحاول لمس مروحة طائرة
  - اثنان من عازبين عن الشرب يستعدون للعشاء
- source_sentence: رجل في منتصف العمر يحلق لحيته في غرفة ذات جدران بيضاء والتي لا
    تبدو كحمام
  sentences:
  - فتى يخطط اسمه على مكتبه
  - رجل ينام
  - المرأة وحدها وهي نائمة في غرفة نومها
- source_sentence: الكلب البني مستلقي على جانبه على سجادة بيج، مع جسم أخضر في المقدمة.
  sentences:
  - شخص طويل القامة
  - المرأة تنظر من النافذة.
  - لقد مات الكلب
model-index:
- name: Omartificial-Intelligence-Space/GATE-AraBert-v1
  results:
  - task:
      type: STS
    dataset:
      name: MTEB STS17 (ar-ar)
      type: mteb/sts17-crosslingual-sts
      config: ar-ar
      split: test
      revision: faeb762787bd10488a50c8b5be4a3b82e411949c
    metrics:
    - type: cosine_pearson
      value: 82.06597171670848
    - type: cosine_spearman
      value: 82.7809395809498
    - type: euclidean_pearson
      value: 79.23996991139896
    - type: euclidean_spearman
      value: 81.5287595404711
    - type: main_score
      value: 82.7809395809498
    - type: manhattan_pearson
      value: 78.95407006608013
    - type: manhattan_spearman
      value: 81.15109493737467
  - task:
      type: STS
    dataset:
      name: MTEB STS22.v2 (ar)
      type: mteb/sts22-crosslingual-sts
      config: ar
      split: test
      revision: d31f33a128469b20e357535c39b82fb3c3f6f2bd
    metrics:
    - type: cosine_pearson
      value: 54.912880452465004
    - type: cosine_spearman
      value: 63.09788380910325
    - type: euclidean_pearson
      value: 57.92665617677832
    - type: euclidean_spearman
      value: 62.76032598469037
    - type: main_score
      value: 63.09788380910325
    - type: manhattan_pearson
      value: 58.0736648155273
    - type: manhattan_spearman
      value: 62.94190582776664
  - task:
      type: STS
    dataset:
      name: MTEB STS22 (ar)
      type: mteb/sts22-crosslingual-sts
      config: ar
      split: test
      revision: de9d86b3b84231dc21f76c7b7af1f28e2f57f6e3
    metrics:
    - type: cosine_pearson
      value: 51.72534929358701
    - type: cosine_spearman
      value: 59.75149627160101
    - type: euclidean_pearson
      value: 53.894835373598774
    - type: euclidean_spearman
      value: 59.44278354697161
    - type: main_score
      value: 59.75149627160101
    - type: manhattan_pearson
      value: 54.076675975406985
    - type: manhattan_spearman
      value: 59.610061143235725
---

# GATE-AraBert-V1

This is **GATE | General Arabic Text Embedding** trained using SentenceTransformers in a **multi-task** setup. The system trains on the **AllNLI** and on the **STS** dataset. It is described in detail in the paper [GATE: General Arabic Text Embedding for Enhanced Semantic Textual Similarity with Hybrid Loss Training](https://huggingface.co/papers/2505.24581).

**Project page:** https://huggingface.co/collections/Omartificial-Intelligence-Space/arabic-matryoshka-embedding-models-666f764d3b570f44d7f77d4e


## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Base model:** [Omartificial-Intelligence-Space/Arabic-Triplet-Matryoshka-V2](https://huggingface.co/Omartificial-Intelligence-Space/Arabic-Triplet-Matryoshka-V2) <!-- at revision 5ce4f80f3ede26de623d6ac10681399dba5c684a -->
- **Maximum Sequence Length:** 512 tokens
- **Output Dimensionality:** 768 tokens
- **Similarity Function:** Cosine Similarity
- **Training Datasets:**
    - [all-nli](https://huggingface.co/datasets/Omartificial-Intelligence-Space/Arabic-NLi-Pair-Class)
    - [sts](https://huggingface.co/datasets/Omartificial-Intelligence-Space/arabic-stsb)
- **Language:** ar


## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```

Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("Omartificial-Intelligence-Space/GATE-AraBert-v1")
# Run inference
sentences = [
    'الكلب البني مستلقي على جانبه على سجادة بيج، مع جسم أخضر في المقدمة.',
    'لقد مات الكلب',
    'شخص طويل القامة',
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 768]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities.shape)
# [3, 3]
```


## Evaluation

| Model                                    | Dim  | # Params. | STS17 | STS22-v2 | Average |
|------------------------------------------|------|-----------|-------|----------|---------|
| Arabic-Triplet-Matryoshka-V2             | 768  | 135M      | 85    | 64       | 75      |
| Arabert-all-nli-triplet-Matryoshka       | 768  | 135M      | 83    | 64       | 74      |
| AraGemma-Embedding-300m                  | 768  | 303M      | 84    | 62       | 73      |
| **GATE-AraBert-V1**                          | 767  | 135M      | 83    | 63       | 73      |
| Marbert-all-nli-triplet-Matryoshka       | 768  | 163M      | 82    | 61       | 72      |
| Arabic-labse-Matryoshka                  | 768  | 471M      | 82    | 61       | 72      |
| AraEuroBert-Small                        | 768  | 210M      | 80    | 61       | 71      |
| E5-all-nli-triplet-Matryoshka            | 384  | 278M      | 80    | 60       | 70      |
| text-embedding-3-large                   | 3072 | -         | 81    | 59       | 70      |
| Arabic-all-nli-triplet-Matryoshka        | 768  | 135M      | 82    | 54       | 68      |
| AraEuroBert-Mid                          | 1151 | 610M      | 83    | 53       | 68      |
| paraphrase-multilingual-mpnet-base-v2    | 768  | 135M      | 79    | 55       | 67      |
| AraEuroBert-Large                        | 2304 | 2.1B      | 79    | 55       | 67      |
| text-embedding-ada-002                   | 1536 | -         | 71    | 62       | 66      |
| text-embedding-3-small                   | 1536 | -         | 72    | 57       | 65      |



## <span style="color:blue">Acknowledgments</span>

The author would like to thank Prince Sultan University for their invaluable support in this project. Their contributions and resources have been instrumental in the development and fine-tuning of these models.


```markdown
## Citation

If you use the GATE, please cite it as follows:

@article{nacar2025gate,
  title={GATE: General Arabic Text Embedding for Enhanced Semantic Textual Similarity with Matryoshka Representation Learning and Hybrid Loss Training},
  author={Nacar, Omer and Koubaa, Anis and Sibaee, Serry and Al-Habashi, Yasser and Ammar, Adel and Boulila, Wadii},
  journal={arXiv preprint arXiv:2505.24581},
  year={2025}
}
```