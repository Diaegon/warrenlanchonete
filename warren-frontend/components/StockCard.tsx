"use client";

import type { StockAssetResult, FinancialMetric } from "@/lib/api";

interface StockCardProps {
  asset: StockAssetResult;
}

function verdictBadgeClass(verdict: string): string {
  const v = verdict.toUpperCase();
  if (v.includes("COMPRA") || v.includes("HOLD")) return "bg-green-500/20 text-green-400 border-green-500/40";
  if (v.includes("VENDA") || v.includes("EVITAR")) return "bg-red-500/20 text-red-400 border-red-500/40";
  return "bg-yellow-500/20 text-yellow-400 border-yellow-500/40";
}

function formatMetricValue(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

function formatDecimal(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(2);
}

function latestMetric(history: FinancialMetric[]): number | null {
  if (!history || history.length === 0) return null;
  const sorted = [...history].sort((a, b) => b.year - a.year);
  return sorted[0]?.value ?? null;
}

export default function StockCard({ asset }: StockCardProps) {
  const latestROE = latestMetric(asset.roe_history);
  const latestMargin = latestMetric(asset.net_margin_history);
  const latestYear = asset.roe_history?.[0]?.year ?? asset.net_margin_history?.[0]?.year;

  return (
    <div className="bg-nubank-card border border-nubank-border rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xl font-bold text-white">{asset.ticker}</span>
            <span
              className={`text-xs font-semibold px-2 py-0.5 rounded border ${verdictBadgeClass(asset.verdict)}`}
            >
              {asset.verdict}
            </span>
          </div>
          <p className="text-nubank-muted text-sm mt-0.5">
            {asset.company_name}
            {asset.sector ? ` · ${asset.sector}` : ""}
          </p>
        </div>
        <div className="text-right">
          <span className="text-nubank-muted text-xs">Peso no portfólio</span>
          <p className="text-white font-bold text-lg">{asset.percentage}%</p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-nubank-dark rounded-lg px-3 py-2">
          <span className="text-nubank-muted text-xs block">
            ROE anual{latestYear ? ` ${latestYear}` : ""}
          </span>
          <span className="text-white font-semibold">
            {formatMetricValue(latestROE)}
          </span>
        </div>
        <div className="bg-nubank-dark rounded-lg px-3 py-2">
          <span className="text-nubank-muted text-xs block">
            Margem líq. anual{latestYear ? ` ${latestYear}` : ""}
          </span>
          <span className="text-white font-semibold">
            {formatMetricValue(latestMargin)}
          </span>
        </div>
        <div className="bg-nubank-dark rounded-lg px-3 py-2">
          <span className="text-nubank-muted text-xs block">CAGR lucro 5a</span>
          <span className="text-white font-semibold">
            {asset.cagr !== null ? formatMetricValue(asset.cagr) : "—"}
          </span>
        </div>
        <div className="bg-nubank-dark rounded-lg px-3 py-2">
          <span className="text-nubank-muted text-xs block">Dív/EBITDA</span>
          <span className="text-white font-semibold">
            {formatDecimal(asset.debt_ebitda)}
          </span>
        </div>
      </div>

      {asset.verdict_detail && (
        <p className="text-nubank-text text-sm leading-relaxed">
          {asset.verdict_detail}
        </p>
      )}

      {asset.buffett_verdict && (
        <div className="border-l-2 border-nubank-purple pl-4">
          <p className="text-nubank-muted text-xs font-semibold uppercase tracking-wider mb-1">
            Veredicto Buffett
          </p>
          <p className="text-nubank-text text-sm leading-relaxed">
            {asset.buffett_verdict}
          </p>
        </div>
      )}

      {asset.citations && asset.citations.length > 0 && (
        <div className="flex flex-col gap-2">
          {asset.citations.map((citation, idx) => (
            <div
              key={idx}
              className="bg-nubank-dark rounded-lg px-4 py-3 border-l-2 border-nubank-purple/50"
            >
              <p className="text-nubank-text text-sm italic leading-relaxed">
                &ldquo;{citation.quote}&rdquo;
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-nubank-muted text-xs">
                  Buffett, {citation.year}
                </span>
                {citation.relevance && (
                  <>
                    <span className="text-nubank-border">·</span>
                    <span className="text-nubank-muted text-xs">
                      {citation.relevance}
                    </span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {asset.retail_adaptation && (
        <div className="bg-nubank-purple/10 rounded-lg px-3 py-2">
          <p className="text-nubank-muted text-xs font-semibold uppercase tracking-wider mb-1">
            Para o investidor comum
          </p>
          <p className="text-nubank-text text-sm">{asset.retail_adaptation}</p>
        </div>
      )}
    </div>
  );
}
