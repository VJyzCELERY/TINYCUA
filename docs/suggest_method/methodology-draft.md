# TinyCUA — Metodologi (Draft)

## 3.1 Arsitektur TinyCUA

TinyCUA adalah arsitektur agen berbasis antrian node sekuensial yang
menerapkan dekomposisi konteks bertingkat (role-scoped context decomposition)
untuk mengurangi hallusinasi pada model bahasa berukuran kecil (4B-9B
parameter). Berbeda dari pendekatan multi-agensi konvensional yang
menggunakan banyak agen independen, TinyCUA menggunakan satu SDK Agent
dengan satu loop eksekusi (TinyCUALoop) yang menjalankan sembilan node
spesialis secara berurutan.

### Gambar 1. Arsitektur TinyCUA

```
┌─────────────────────────────────────────────────────────────────────┐
│                          TinyCUA Agent                              │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     TinyCUALoop                               │  │
│  │                                                               │  │
│  │   User Query                                                  │  │
│  │       │                                                       │  │
│  │       ▼                                                       │  │
│  │  ┌─────────────────────┐                                      │  │
│  │  │   QueryAnalyst      │  ← DecisionNode                      │  │
│  │  │   (2-step decision) │                                      │  │
│  │  └─────────┬───────────┘                                      │  │
│  │            │                                                   │  │
│  │     ┌──────┼──────────┐                                       │  │
│  │     ▼      ▼          ▼                                       │  │
│  │  passthrough  worker   uncertain                               │  │
│  │     │      │          │                                        │  │
│  │     │      ▼          └──→ waits for user continuation         │  │
│  │     │  ┌─────────────────────┐                                 │  │
│  │     │  │      Worker         │  ← DecisionNode                 │  │
│  │     │  │   (2-step decision) │                                 │  │
│  │     │  └─────────┬───────────┘                                 │  │
│  │     │            │                                             │  │
│  │     │   ┌────────┼────────────┐                                │  │
│  │     │   ▼        ▼            ▼                                │  │
│  │     │  task_    task_       proceed                            │  │
│  │     │  creation recreation  execution                          │  │
│  │     │   │        │            │                                │  │
│  │     │   ▼        ▼            │                                │  │
│  │     │  TaskCreate  │          │                                │  │
│  │     │     │        │          │                                │  │
│  │     │     ▼        ▼          │                                │  │
│  │     │  ┌──────────────────┐   │                                │  │
│  │     │  │  TaskAnalyzer    │   │  ← ProcessNode                 │  │
│  │     │  └────────┬─────────┘   │                                │  │
│  │     │           ▼              │                                │  │
│  │     │  ┌──────────────────┐    │                                │  │
│  │     │  │ AnalysisEffort   │    │  ← controls decomposition      │  │
│  │     │  │ (pass_limit:     │    │    passes (none/low/med/high)  │  │
│  │     │  │  0/1/2/3)        │    │                                │  │
│  │     │  └────────┬─────────┘    │                                │  │
│  │     │           │              │                                │  │
│  │     │    ┌──────┴──────┐       │                                │  │
│  │     │    ▼             ▼       │                                │  │
│  │     │  TaskAssessor  TaskAnalyzer  (loop until pass_limit)      │  │
│  │     │    └──────┬──────┘       │                                │  │
│  │     │           ▼              │                                │  │
│  │     │  ┌──────────────────┐    │                                │  │
│  │     │  │  TaskExecutor    │◄───┘  ← ProcessNode (ReAct)         │  │
│  │     │  │  (execute task   │                                     │  │
│  │     │  │   with tools)    │                                     │  │
│  │     │  └────────┬─────────┘                                     │  │
│  │     │           ▼                                               │  │
│  │     │  ┌──────────────────┐                                     │  │
│  │     │  │ ResultReviewer   │  ← ProcessNode                      │  │
│  │     │  │ accept|retry|    │                                     │  │
│  │     │  │ replan|open_q    │                                     │  │
│  │     │  └────────┬─────────┘                                     │  │
│  │     │           │                                               │  │
│  │     │     ┌─────┴────────┐                                      │  │
│  │     │     ▼              ▼                                      │  │
│  │     │  retry→back    root done                                  │  │
│  │     │  to Executor      │                                       │  │
│  │     │                   ▼                                       │  │
│  │     │  ┌──────────────────┐                                     │  │
│  │     │  │ ResultAggregation│  ← ProcessNode                      │  │
│  │     │  │ (BFS traversal)  │                                     │  │
│  │     │  └────────┬─────────┘                                     │  │
│  │     │           ▼                                               │  │
│  │     ▼  ┌──────────────────┐                                     │  │
│  │   ┌────┤   ResponseNode   │  ← ProcessNode (terminal)           │  │
│  │   │    │  (synthesize     │                                     │  │
│  │   │    │   final answer)  │──→ may suspend for InfoDigester     │  │
│  │   │    └──────────────────┘                                     │  │
│  │   │              │                                              │  │
│  │   └──────────────┘                                              │  │
│  │         │                                                       │  │
│  │         ▼                                                       │  │
│  │    ┌──────────────────┐                                         │  │
│  │    │ InformationDigest│  ← ProcessNode (optional, on-demand)    │  │
│  │    │ (enhanced context│                                         │  │
│  │    │  retrieval)      │                                         │  │
│  │    └──────────────────┘                                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Gambar 2. Aliran Konteks (Context Flow)

```
  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
  │   Node A      │      │   Node B      │      │   Node C      │
  │               │      │               │      │               │
  │ session_ctx = │      │ session_ctx = │      │ session_ctx = │
  │ prior + input │      │ prior + input │      │ prior + input │
  │       + output│      │       + output│      │       + output│
  └───────┬───────┘      └───────┬───────┘      └───────┬───────┘
          │                       │                       │
          │  propagate            │  propagate            │  propagate
          │  (prior+input)        │  (prior+input)        │  (prior+input)
          ▼                       ▼                       ▼
    ┌───────────┐           ┌───────────┐           ┌───────────┐
    │  Parent    │           │  Parent    │           │  Parent    │
    │  Session   │           │  Session   │           │  Session   │
    └───────────┘           └───────────┘           └───────────┘

          │  forward               │  forward
          │  (output)              │  (output)
          ▼                        ▼
    ┌───────────┐           ┌───────────┐
    │  Node B    │           │  Node C    │
    │  input     │           │  input     │
    └───────────┘           └───────────┘
```

Setiap node membagi session context-nya menjadi tiga segmen:
- **prior_context**: akumulasi dari node sebelumnya
- **input_segment**: data yang diterima saat node dimulai
- **output_segment**: hasil produksi node saat eksekusi

Saat node selesai, prior+input propagate ke parent/root, sementara
output diteruskan ke node berikutnya sebagai input.

---

## 3.2 Penjelasan Arsitektur

### 3.2.1 TinyCUALoop dan NodeQueue

TinyCUA berjalan di atas satu SDK Agent tanpa memodifikasi API-nya.
TinyCUALoop mewarisi BaseLoop SDK dan menjalankan NodeQueue — antrian
node sekuensial di mana node aktif selalu berada di posisi pertama.
Setiap iterasi loop: (1) ambil node saat ini, (2) bangun pesan input,
(3) resolve tools berdasarkan node policy, (4) panggil LLM, (5) validasi
output, (6) jalankan on_complete untuk transisi queue.

### 3.2.2 Dua Tipe Node

TinyCUA menggunakan dua kelas abstrak node:

**DecisionNode** — menggunakan proses keputusan dua langkah:
  (1) analysis call: LLM menganalisis request
  (2) verdict call: LLM memanggil classification tool dengan label
  (3) dispatch: RouteMap memanggil handler sesuai label

QueryAnalyst dan Worker keduanya adalah DecisionNode.

**ProcessNode** — langsung mengeksekusi tanpa routing decision.
TaskAnalyzer, TaskExecutor, ResultReviewer, dan lainnya adalah ProcessNode.

### 3.2.3 QueryAnalyst — Entry Point

QueryAnalyst adalah node pertama yang dijalankan setiap kali ada input
pengguna. Ia melakukan dua hal:
1. **Precheck**: apakah ada mandatory_passthrough? Jika ya, forward
   deterministically ke target node tanpa LLM call.
2. **Klasifikasi**: jalankan two-step decision → pilih dari label
   `passthrough`, `worker`, atau `uncertain`.

QueryAnalyst tidak merencanakan atau mengeksekusi tugas — ia hanya
mengarahkan lalu lintas.

### 3.2.4 Worker — Sub-agent Orchestration

Worker adalah DecisionNode yang mengelola seluruh siklus hidup task.
Worker tidak mengeksekusi task secara langsung, tetapi merutekan ke
node-node yang sesuai:

- **task_creation**: Task Create → Task Analyzer → Analysis Effort
  → Task Executor → Result Reviewer → Response
- **task_recreation**: Task Analyzer (+TaskInit tools) → Analysis Effort
  → Task Executor → Result Reviewer → Response
- **task_reanalysis**: Task Analyzer (tanpa TaskInit) → Analysis Effort
  → Task Executor → Result Reviewer → Response
- **proceed_execution**: langsung ke Task Executor → Result Reviewer
  → Response
- **passthrough**: forward input ke node worker-owned berikutnya

### 3.2.5 AnalysisEffort — Gated Decomposition Loop

AnalysisEffortNode mengontrol berapa kali loop [TaskAssessor → TaskAnalyzer]
berjalan sebelum eksekusi dimulai. Level effort:
- **none** (0): langsung ke TaskExecutor
- **low** (1 pass): satu kali TaskAssessor + TaskAnalyzer
- **medium** (2 pass): dua kali
- **high** (3 pass): tiga kali

Ini memungkinkan trade-off antara kedalaman analisis dan latency.

### 3.2.6 Task Executor — ReAct Execution

TaskExecutor mengeksekusi satu task dengan context yang terisolasi.
Ia menggunakan pola ReAct (Reason + Act) dengan tools yang dibatasi
hanya untuk scope task saat ini. TaskExecutor tidak melihat task tree
secara keseluruhan — hanya task aktif dan konteksnya.

### 3.2.7 ResultReviewer — Quality Gate

ResultReviewer mengevaluasi hasil eksekusi dan memutuskan:
- **accept**: task selesai, lanjut ke task berikutnya atau aggregasi
- **retry**: ulang eksekusi dengan failure context (max 5 kali)
- **replan**: minta TaskAssessor + TaskAnalyzer menyusun ulang
  dekomposisi untuk task aktif (lokal, bukan global)
- **open_question**: tanyakan ke pengguna (HITL) jika threshold
  kegagalan tercapai

### 3.2.8 ResultAggregation dan Response

Setelah root task diterima, ResultAggregationNode melakukan traversal
BFS right-to-left pada task tree, mengumpulkan semua task summaries,
accepted results, dan artifacts. Hasilnya berupa AggregatedResult yang
diteruskan ke ResponseNode untuk disintesis menjadi jawaban akhir.

ResponseNode dapat menangguhkan dirinya sendiri dan meminta
InformationDigestion jika konteks yang tersedia tidak mencukupi
(suspend → prepend InfoDigest → resume).

### 3.2.9 Propagasi Konteks

TinyCUA menggunakan model segmented context yang dikontrol oleh
PropagationRule. Tiap node menghasilkan tiga segmen:
- prior_context (dari parent/previous nodes)
- input_segment (diterima saat node mulai)
- output_segment (dihasilkan saat eksekusi)

Saat node selesai: prior+input propagate ke parent/root, output
diteruskan ke node berikutnya. Mekanisme deduplikasi menggunakan
origin_record_id untuk mencepat konteks duplikat.

### 3.2.10 MandatoryPassthrough — HITL Mechanism

MandatoryPassthrough adalah mekanisme deterministic yang memungkinkan
node memanggil pengguna untuk input tambahan tanpa melalui LLM
klasifikasi. Berguna untuk:
- User continuation (jawaban atas pertanyaan terbuka)
- Recovery dari open_question ResultReviewer
- Restart QueryAnalyst jika passthrough stale
