import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'

const PIPELINE_DIAGRAM = `flowchart TD
    START(["Input: JD + candidates.jsonl (100K)"])

    subgraph S0["STAGE 0 — Fraud gate (stream all 100K)"]
        HP["is_honeypot()\\n• timeline mismatch\\n• notice >180d\\n• endorsement fraud"]
        GH["is_ghost_unavailable()\\ninactive 6mo + RR ≤5%"]
        HP --> SKIP0["recall score = 0\\nor skip scoring"]
        GH --> PEN0["×0.06 penalty"]
    end

    subgraph S1["STAGE 1 — Hybrid recall → ~5K shortlist"]
        STREAM["iter_candidates()\\n3-pass streaming\\n~280MB RAM peak"]
        BM25["StreamingBM25 +\\nBM25Index"]
        LEX["Lexical JD overlap"]
        TITLE["Title score gate"]
        FUSE["Fuse scores → heap top-K"]
        STREAM --> BM25 --> FUSE
        LEX --> FUSE
        TITLE --> FUSE
    end

    subgraph S2["STAGE 2 — Semantic (shortlist only)"]
        TFIDF["TfidfVectorizer\\ncosine vs JD"]
        ST["Optional ST embeddings\\nmmap .npy (60% blend)"]
        TFIDF --> SEM["semantic score"]
        ST --> SEM
    end

    subgraph S3["STAGE 3 — Precision scoring"]
        RULE["_deep_score()\\ntitle 30% + career 24%\\n+ skills 18% + exp 10%\\n+ location 8% + semantic 6%..."]
        MULT["× behavioral\\n× penalties\\n× career_boost × jd_fit"]
        FEAT["extract_features()\\n20 features"]
        GBM["HistGradientBoosting\\nLTR predict"]
        BLEND["blended = 0.52×rule + 0.48×LTR"]
        RULE --> MULT --> BLEND
        FEAT --> GBM --> BLEND
    end

    subgraph S4["STAGE 4 — Audit + demotion"]
        AUDIT["cross_check_candidate()\\nflags + confidence + fit_tier"]
        SORT["Sort by blended score"]
        DEMOTE["clean → soft_demoted → hard_demoted"]
        TOP100["Take top 100"]
        AUDIT --> SORT --> DEMOTE --> TOP100
    end

    subgraph S5["STAGE 5 — Reasoning"]
        RB2["reasoning_builder.py\\nrule-based (always)"]
        OLL2["ollama_reasoning.py\\noptional: top 10 auto\\non-demand ranks 11–100"]
        RB2 --> OLL2
    end

    subgraph OUT["Output"]
        NORM["Normalize display scores\\n1.0 → 0.208 by rank"]
        CSV2["submission.csv"]
        QR["quality_report\\nhoneypot_rate, submission_ready"]
        CACHE["_ranking_cache (UI)"]
    end

    START --> S0 --> S1 --> S2 --> S3 --> S4 --> S5 --> OUT
    NORM --> CSV2 & QR & CACHE`

const SYSTEM_DIAGRAM = `flowchart TB
    subgraph UI["React UI (Vite + Tailwind)"]
        DASH["Dashboard"]
        MATCH["Matches + Run Ranking"]
        ARCH["Architecture (this page)"]
    end

    subgraph API["FastAPI :8000"]
        R(event["POST /challenge/rank"])
        EP2(event2["GET /challenge/matches"])
        EP3(event3["POST .../reasoning"])
    end

    subgraph CORE["Ranking core (CPU, offline-safe)"]
        RANK["rank.py / challenge_ranker.py"]
        FRAUD["fraud_detector.py"]
        BM25["bm25_recall.py"]
        LTR["ltr_ranker.py"]
        AUD["rank_auditor.py"]
    end

    subgraph OPT["Optional (UI only)"]
        OLL["Ollama llama3.2 localhost"]
    end

    subgraph DATA["File-backed data"]
        JSONL[("candidates.jsonl 100K")]
        CSV[("submission.csv")]
        CACHE2[("ranker_cache/")]
    end

    UI --> API --> RANK
    RANK --> FRAUD & BM25 & LTR & AUD
    RANK --> JSONL
    RANK --> CSV & CACHE2
    EP3 --> OLL`

function MermaidBlock({ id, chart, title }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!ref.current) return
    ref.current.removeAttribute('data-processed')
    ref.current.innerHTML = chart
    mermaid
      .run({ nodes: [ref.current], suppressErrors: true })
      .catch(() => {})
  }, [chart, id])

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6 overflow-x-auto">
      {title && <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>}
      <div ref={ref} id={id} className="mermaid flex justify-center min-w-[640px]" />
    </div>
  )
}

function Section({ title, children }) {
  return (
    <section className="mb-10">
      <h2 className="text-xl font-bold text-gray-900 border-b border-gray-200 pb-2 mb-4">{title}</h2>
      {children}
    </section>
  )
}

function StageCard({ stage, title, file, summary, checks, output }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex flex-wrap items-baseline gap-2 mb-2">
        <span className="text-xs font-bold uppercase tracking-wide text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
          {stage}
        </span>
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      </div>
      {file && (
        <p className="text-sm text-gray-500 font-mono mb-3">{file}</p>
      )}
      <p className="text-gray-700 mb-3">{summary}</p>
      {checks?.length > 0 && (
        <ul className="list-disc list-inside text-sm text-gray-600 space-y-1 mb-3">
          {checks.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
      {output && (
        <p className="text-sm text-gray-800 bg-gray-50 rounded px-3 py-2">
          <span className="font-medium">Output: </span>
          {output}
        </p>
      )}
    </div>
  )
}

export default function Architecture() {
  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'neutral',
      flowchart: { curve: 'basis', padding: 12, htmlLabels: true },
      securityLevel: 'loose',
    })
  }, [])

  return (
    <div className="px-4 sm:px-0 pb-16">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Pipeline Architecture</h1>
        <p className="mt-2 text-gray-600 max-w-3xl">
          TalentLens ranks the top 100 candidates from 100,000 profiles for a Senior AI Engineer role.
          The pipeline is designed for hackathon constraints: CPU-only submission path, under 5 minutes,
          no network at rank time, and zero honeypots in the top 100.
        </p>
      </div>

      <Section title="End-to-end pipeline">
        <MermaidBlock id="pipeline-main" chart={PIPELINE_DIAGRAM} />
        <p className="mt-4 text-sm text-gray-600">
          Every candidate is streamed once from <code className="bg-gray-100 px-1 rounded">candidates.jsonl</code>.
          Fraud checks run on the full corpus; expensive semantic and LTR scoring run only on the ~5K recall shortlist.
        </p>
      </Section>

      <Section title="System overview">
        <MermaidBlock id="pipeline-system" chart={SYSTEM_DIAGRAM} title="UI → API → ranker → files" />
      </Section>

      <Section title="Stage-by-stage detail">
        <div className="grid gap-4 lg:grid-cols-2">
          <StageCard
            stage="Stage 0"
            title="Fraud gate"
            file="app/services/fraud_detector.py"
            summary="First pass over all 100K records. Catches synthetic honeypots and ghost profiles before they consume recall budget."
            checks={[
              'is_honeypot(): timeline mismatch (education vs work), notice period >180 days, endorsement fraud patterns',
              'is_ghost_unavailable(): inactive 6+ months with response rate ≤5%',
              'Honeypots: recall forced to 0 or candidate skipped from scoring',
              'Ghosts: ×0.06 behavioral penalty applied in precision stage',
            ]}
            output="Fraud flags attached; honeypots never reach top 100"
          />
          <StageCard
            stage="Stage 1"
            title="Hybrid recall → ~5K shortlist"
            file="app/services/bm25_recall.py · challenge_ranker.iter_candidates()"
            summary="Three-pass streaming keeps peak RAM near 280MB. Combines BM25, lexical JD overlap, and title relevance into a fused recall score; min-heap retains top-K."
            checks={[
              'Pass 1: stream jsonl, accumulate BM25 corpus stats',
              'Pass 2: build BM25Index, score each candidate',
              'Pass 3: fuse BM25 + lexical overlap + title gate → heap top ~5000',
              'Title gate drops clearly irrelevant roles early',
            ]}
            output="~5,000 candidates for semantic + precision stages"
          />
          <StageCard
            stage="Stage 2"
            title="Semantic scoring (shortlist only)"
            file="challenge_ranker.py · optional scripts/precompute_embeddings.py"
            summary="TF-IDF cosine similarity between candidate text and job description. Optional Sentence-Transformer embeddings (mmap .npy) blend at 60% when precomputed offline."
            checks={[
              'TfidfVectorizer fit on JD + shortlist corpus',
              'Cosine similarity → semantic_score ∈ [0, 1]',
              'Optional ST embeddings: 0.4×TF-IDF + 0.6×embedding cosine',
              'Not required for submission — rank.py works without network or GPU',
            ]}
            output="semantic_score fed into rule weights (6%) and LTR features"
          />
          <StageCard
            stage="Stage 3"
            title="Precision scoring (rule + LTR blend)"
            file="challenge_ranker._deep_score() · app/services/ltr_ranker.py"
            summary="Hand-tuned rule score captures JD-specific signals; HistGradientBoosting LTR learns from 20 engineered features. Final score is a 52/48 blend."
            checks={[
              'Rule weights: title 30%, career 24%, skills 18%, experience 10%, location 8%, semantic 6%, plus behavioral modifiers',
              'Multipliers: behavioral fit, fraud penalties, career_boost, jd_fit',
              'extract_features(): 20 numeric features for LTR',
              'blended = 0.52 × rule_score + 0.48 × ltr_score',
            ]}
            output="blended_score per shortlist candidate"
          />
          <StageCard
            stage="Stage 4"
            title="Audit, demotion, top 100"
            file="app/services/rank_auditor.py"
            summary="cross_check_candidate() assigns audit flags, confidence tier, and fit_tier. Sorted list is demoted: clean → soft_demoted → hard_demoted, then top 100 taken."
            checks={[
              'Flags: keyword stuffing, timeline gaps, skill inflation, etc.',
              'confidence: high / medium / low based on signal agreement',
              'fit_tier: strong / moderate / weak vs JD',
              'Demotion pushes flagged profiles down without dropping valid strong matches',
            ]}
            output="Ordered top 100 with audit metadata"
          />
          <StageCard
            stage="Stage 5"
            title="Reasoning"
            file="app/services/reasoning_builder.py · ollama_reasoning.py"
            summary="Rule-based reasoning is always generated (submission-safe). Ollama (llama3.2 on localhost) optionally enriches top 10 on rank; ranks 11–100 on demand via API."
            checks={[
              'reasoning_builder: deterministic bullets from scores + flags',
              'ollama_reasoning: POST to localhost:11434, fallback to rules on failure',
              'UI default: Ollama top 10 (~1.5–2 min total rank)',
              'On-demand: POST /matches/{id}/reasoning (~3–5s per candidate)',
            ]}
            output="reasoning text + score_breakdown in CSV and UI cache"
          />
        </div>
      </Section>

      <Section title="Scoring formula">
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Component</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Weight</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Signals</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {[
                ['Title match', '30%', 'Senior AI / ML Engineer titles, level alignment'],
                ['Career trajectory', '24%', 'Company tier, progression, IR/product evidence'],
                ['Skills overlap', '18%', 'PyTorch, LLMs, RAG, MLOps vs JD keywords'],
                ['Experience', '10%', 'Years, relevance, project depth'],
                ['Location', '8%', 'Remote/hybrid/on-site vs JD'],
                ['Semantic', '6%', 'TF-IDF (+ optional ST blend)'],
                ['Behavioral', 'multiplier', 'Response rate, activity, ghost penalty'],
                ['LTR blend', '48%', 'HistGradientBoosting on 20 features'],
                ['Rule blend', '52%', 'Weighted sum above'],
              ].map(([comp, weight, signals]) => (
                <tr key={comp}>
                  <td className="px-4 py-3 font-medium text-gray-900">{comp}</td>
                  <td className="px-4 py-3 text-indigo-600 font-mono">{weight}</td>
                  <td className="px-4 py-3 text-gray-600">{signals}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-gray-600">
          Display scores in <code className="bg-gray-100 px-1 rounded">submission.csv</code> are rank-normalized
          (rank 1 → 1.0, rank 100 → ~0.208) for judge readability; internal blended scores drive ordering.
        </p>
      </Section>

      <Section title="Module map">
        <div className="bg-slate-900 text-slate-100 rounded-lg p-5 font-mono text-sm overflow-x-auto leading-relaxed">
          <pre>{`TalentLens/
├── rank.py                      CLI entry (submit path: CPU, no network)
├── app/
│   ├── api/v1/endpoints/challenge.py   REST: rank, matches, reasoning
│   └── services/
│       ├── challenge_ranker.py    v4 pipeline orchestrator
│       ├── fraud_detector.py      Stage 0 honeypot + ghost
│       ├── bm25_recall.py         Stage 1 streaming BM25
│       ├── ltr_ranker.py          Stage 3 HistGradientBoosting LTR
│       ├── rank_auditor.py        Stage 4 audit + demotion
│       ├── reasoning_builder.py   Stage 5 rule reasoning
│       └── ollama_reasoning.py    Stage 5 optional LLM enrichment
├── data/
│   ├── candidates.jsonl           100K profiles (challenge input)
│   ├── submission.csv             top 100 output
│   └── ranker_cache/              UI ranking cache
└── frontend/                      React dashboard (this Architecture tab)`}</pre>
        </div>
      </Section>

      <Section title="Data storage">
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Store</th>
                <th className="px-4 py-3 text-left font-semibold">Used for</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-4 py-3 font-mono text-gray-800">candidates.jsonl</td>
                <td className="px-4 py-3 text-gray-600">Challenge ranking input (100K lines, streamed)</td>
              </tr>
              <tr>
                <td className="px-4 py-3 font-mono text-gray-800">submission.csv</td>
                <td className="px-4 py-3 text-gray-600">Top 100 output: rank, candidate_id, score, reasoning</td>
              </tr>
              <tr>
                <td className="px-4 py-3 font-mono text-gray-800">data/ranker_cache/</td>
                <td className="px-4 py-3 text-gray-600">Cached ranking JSON for Matches UI</td>
              </tr>
              <tr>
                <td className="px-4 py-3 font-mono text-gray-800">talentlens.db (SQLite)</td>
                <td className="px-4 py-3 text-gray-600">Legacy ATS demo only — not used by challenge ranker</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="API endpoints">
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Method</th>
                <th className="px-4 py-3 text-left font-semibold">Path</th>
                <th className="px-4 py-3 text-left font-semibold">Purpose</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-4 py-3 font-mono text-green-700">POST</td>
                <td className="px-4 py-3 font-mono">/api/v1/challenge/rank</td>
                <td className="px-4 py-3 text-gray-600">Run full pipeline; optional Ollama top-N</td>
              </tr>
              <tr>
                <td className="px-4 py-3 font-mono text-blue-700">GET</td>
                <td className="px-4 py-3 font-mono">/api/v1/challenge/matches</td>
                <td className="px-4 py-3 text-gray-600">Load cached top 100 with reasoning</td>
              </tr>
              <tr>
                <td className="px-4 py-3 font-mono text-green-700">POST</td>
                <td className="px-4 py-3 font-mono">/api/v1/challenge/matches/{'{id}'}/reasoning</td>
                <td className="px-4 py-3 text-gray-600">On-demand Ollama reasoning for one candidate</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Constraints & benchmark">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Rank time (100K)', '~62s', 'CPU, no Ollama'],
            ['Peak RAM', '~280 MB', 'Streaming jsonl'],
            ['Honeypots in top 100', '0%', 'Disqualify if >10%'],
            ['Quality score', '100', 'submission_ready'],
          ].map(([label, value, note]) => (
            <div key={label} className="bg-white border border-gray-200 rounded-lg p-4 text-center">
              <p className="text-2xl font-bold text-indigo-600">{value}</p>
              <p className="font-medium text-gray-900 mt-1">{label}</p>
              <p className="text-xs text-gray-500 mt-1">{note}</p>
            </div>
          ))}
        </div>
        <ul className="mt-4 list-disc list-inside text-sm text-gray-600 space-y-1">
          <li>
            <strong>Submission path</strong> (<code className="bg-gray-100 px-1 rounded">python rank.py</code>):
            CPU only, ≤5 min, no network, no Ollama required.
          </li>
          <li>
            <strong>Demo UI path</strong>: optional Ollama on localhost for richer reasoning; defaults to top 10
            auto-enrichment to keep rank under ~2 minutes.
          </li>
          <li>
            <strong>Honeypot safety</strong>: Stage 0 fraud gate + Stage 4 audit; benchmark shows 0 honeypots
            in delivered top 100.
          </li>
        </ul>
      </Section>

      <Section title="Tech stack">
        <div className="flex flex-wrap gap-2">
          {[
            'Python 3.11',
            'FastAPI',
            'scikit-learn',
            'React 18',
            'Vite',
            'Tailwind CSS',
            'Ollama (optional)',
            'JSONL file I/O',
          ].map((t) => (
            <span
              key={t}
              className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-indigo-50 text-indigo-800"
            >
              {t}
            </span>
          ))}
        </div>
      </Section>
    </div>
  )
}
