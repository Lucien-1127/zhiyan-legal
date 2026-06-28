/**
 * bridge.js — committee/ API 前端橋接層
 *
 * 讓儀表板從靜態 JSON 或動態 API 拉取合議庭報告。
 * 自動降級：API 不通 → fallback 到本地 committee_report.json
 */

const COMMITTEE_API = "http://localhost:8000/api/committee/run";
const LOCAL_REPORT = "./committee_report.json";

// ── 主要入口 ──

export async function fetchCommitteeReport(options = {}) {
  const {
    apiUrl = COMMITTEE_API,
    localPath = LOCAL_REPORT,
    preferApi = false,         // true = 打 API, false = 先讀本地 JSON
    query = "",
    models = ["agnes-k1", "agnes-k2"],
    normalization = { citation: true, terminology: true, semantic: false },
    synthesis = "mark",
    agreeThreshold = 0.75,
  } = options;

  // 1) 嘗試 API（如果 preferApi 或 query 有值）
  if (preferApi || query.trim()) {
    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          models,
          normalization,
          synthesis,
          agree_threshold: agreeThreshold,
          temperature: 0.3,
          max_tokens: 1024,
        }),
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      return normalizeApiResponse(data);
    } catch (err) {
      console.warn("API 不可用，降級到本地 JSON：", err.message);
      // fall through to local JSON
    }
  }

  // 2) 降級：讀本地 committee_report.json
  try {
    const res = await fetch(localPath, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return normalizeLocalReport(data);
  } catch (err) {
    return { error: true, message: `無法載入報告：${err.message}` };
  }
}

// ── 正規化 API Response（對應 CommitteeResponse schema）──

function normalizeApiResponse(data) {
  const consensus = data.synthesis?.consensus ?? [];
  const divergence = data.synthesis?.divergence ?? [];
  const unique = data.synthesis?.unique ?? [];

  const totalClaims = consensus.length + divergence.length + unique.length;
  const consensusRate = totalClaims > 0 ? consensus.length / totalClaims : 0;

  // 安全 unknown 計數（從 divergence 中撈）
  const safetyUnknownCount = divergence.filter(
    (d) => d.position_a === "safety_unknown" || d.position_b === "safety_unknown"
  ).length;

  return {
    source: "api",
    queryId: data.query_id,
    query: data.query,
    timestamp: new Date().toISOString(),
    summary: {
      total: totalClaims,
      consensus: consensus.length,
      divergence: divergence.length,
      unique: unique.length,
      consensus_rate: round(consensusRate * 100, 1),
      safety_unknown_count: safetyUnknownCount,
      models: Object.keys(data.models ?? {}),
    },
    synthesis: {
      consensus: consensus.map((c) => ({
        claim: c.claim,
        models: c.models,
      })),
      divergence: divergence.map((d) => ({
        claim: d.claim,
        modelA: { name: d.model_a, position: d.position_a },
        modelB: { name: d.model_b, position: d.position_b },
      })),
      unique: unique.map((u) => ({
        claim: u.claim,
        model: u.model,
      })),
    },
    models: Object.entries(data.models ?? {}).map(([name, m]) => ({
      name,
      status: m.status,
      elapsed_s: m.elapsed_s,
      tokens_in: m.tokens_in,
      tokens_out: m.tokens_out,
    })),
    meta: {
      elapsed_s: data.elapsed_total_s,
      norm_layers: data.norm_layers_applied,
      synthesis_mode: data.synthesis_mode,
      quota: data.quota,
    },
  };
}

// ── 正規化本地 JSON Report ──

function normalizeLocalReport(data) {
  const reports = data.reports ?? [];
  const totalQueries = data.total_queries ?? reports.length;

  let totalConsensus = 0;
  let totalDivergence = 0;
  let totalBlind = 0;
  let totalSafetyUnknown = 0;
  const divergenceItems = [];

  for (const r of reports) {
    totalConsensus += r.consensus ?? 0;
    totalDivergence += r.disagreement ?? 0;
    totalBlind += r.blind_spot ?? 0;

    // 收集分歧明細
    if (r.disagreements) {
      for (const d of r.disagreements) {
        const isSafety =
          d.position_a === "safety_unknown" || d.position_b === "safety_unknown";
        if (isSafety) totalSafetyUnknown++;
        divergenceItems.push({
          queryId: r.query_id,
          category: r.category,
          ...d,
          safety: isSafety,
        });
      }
    }
  }

  return {
    source: "local_json",
    timestamp: new Date().toISOString(),
    summary: {
      total: totalQueries,
      consensus: totalConsensus,
      divergence: totalDivergence,
      blind_spot: totalBlind,
      consensus_rate:
        totalQueries > 0 ? round((totalConsensus / totalQueries) * 100, 1) : 0,
      divergence_rate:
        totalQueries > 0 ? round((totalDivergence / totalQueries) * 100, 1) : 0,
      safety_unknown_count: totalSafetyUnknown,
    },
    divergenceItems,
    meta: {
      generated_at: data.metadata?.generated_at ?? null,
    },
  };
}

// ── 工具函數 ──

function round(n, d) {
  return Math.round(n * 10 ** d) / 10 ** d;
}

/**
 * 快速檢測 API 是否在線
 */
export async function healthCheck(url = "http://localhost:8000/health") {
  try {
    const res = await fetch(url, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}
