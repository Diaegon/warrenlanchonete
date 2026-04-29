"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import GradeDisplay from "@/components/GradeDisplay";
import AlertBanner from "@/components/AlertBanner";
import StockCard from "@/components/StockCard";
import FIICard from "@/components/FIICard";
import TesourCard from "@/components/TesourCard";
import type {
  PortfolioAnalysisResponse,
  AssetResult,
  StockAssetResult,
  FIIAssetResult,
  TesourAssetResult,
} from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function isStock(asset: AssetResult): asset is StockAssetResult {
  return asset.asset_type === "STOCK";
}

function isFII(asset: AssetResult): asset is FIIAssetResult {
  return asset.asset_type === "FII";
}

function isTesouro(asset: AssetResult): asset is TesourAssetResult {
  return asset.asset_type === "TESOURO";
}

export default function ReportPage() {
  const router = useRouter();
  const [report, setReport] = useState<PortfolioAnalysisResponse | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("warren_report");
    if (!raw) {
      router.replace("/");
      return;
    }
    try {
      const parsed = JSON.parse(raw) as PortfolioAnalysisResponse;
      setReport(parsed);
    } catch {
      router.replace("/");
    }
  }, [router]);

  async function handleDownloadPDF() {
    if (!report || isDownloading) return;
    setDownloadError(null);
    setIsDownloading(true);

    try {
      const rawReport = sessionStorage.getItem("warren_report");
      if (!rawReport) throw new Error("Dados do relatório não encontrados.");

      const parsed = JSON.parse(rawReport) as PortfolioAnalysisResponse;
      const assets = parsed.assets.map((a) => ({
        ticker: a.ticker,
        type: a.asset_type,
        percentage: a.percentage,
      }));

      const res = await fetch(
        `${BASE_URL}/api/portfolio/analyze?format=pdf`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ assets }),
        }
      );

      if (!res.ok) {
        throw new Error("Não foi possível gerar o PDF.");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "warren-lanchonete-relatorio.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(
        err instanceof Error ? err.message : "Erro ao baixar PDF."
      );
    } finally {
      setIsDownloading(false);
    }
  }

  function handleNovaAnalise() {
    sessionStorage.removeItem("warren_report");
    router.push("/");
  }

  if (!report) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="flex flex-col items-center gap-4">
          <svg
            className="animate-spin h-8 w-8 text-nubank-purple"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-label="Carregando relatório"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <p className="text-nubank-muted text-sm">Carregando relatório...</p>
        </div>
      </div>
    );
  }

  const stockAssets = report.assets.filter(isStock);
  const fiiAssets = report.assets.filter(isFII);
  const tesourAssets = report.assets.filter(isTesouro);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white">
            Resultado da análise
          </h1>
          <p className="text-nubank-muted text-sm mt-1">
            Baseado na filosofia de Buffett
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleNovaAnalise}
            className="px-4 py-2.5 rounded-lg border border-nubank-border text-nubank-text text-sm font-medium hover:border-nubank-purple hover:text-white transition-colors"
          >
            Nova análise
          </button>
          <button
            type="button"
            onClick={handleDownloadPDF}
            disabled={isDownloading}
            className="px-4 py-2.5 rounded-lg bg-nubank-purple text-white text-sm font-medium hover:bg-purple-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {isDownloading ? (
              <>
                <svg
                  className="animate-spin h-4 w-4"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Gerando PDF...
              </>
            ) : (
              <>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  aria-hidden="true"
                >
                  <path
                    d="M7 1V9M7 9L4 6M7 9L10 6M2 11H12"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Baixar PDF
              </>
            )}
          </button>
        </div>
      </div>

      {downloadError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
          <p className="text-red-400 text-sm">{downloadError}</p>
        </div>
      )}

      <div className="bg-nubank-card border border-nubank-border rounded-2xl p-6 sm:p-8 flex flex-col sm:flex-row items-center gap-6 sm:gap-10">
        <GradeDisplay grade={report.portfolio_grade} />
        <div className="flex-1 text-center sm:text-left">
          <h2 className="text-white font-bold text-lg mb-2">
            Resumo do portfólio
          </h2>
          <p className="text-nubank-text text-sm leading-relaxed">
            {report.portfolio_summary}
          </p>
        </div>
      </div>

      {report.portfolio_alerts && report.portfolio_alerts.length > 0 && (
        <div className="flex flex-col gap-3">
          <h2 className="text-nubank-muted text-sm font-semibold uppercase tracking-wider">
            Alertas do oráculo
          </h2>
          {report.portfolio_alerts.map((alert, idx) => (
            <AlertBanner key={idx} message={alert} />
          ))}
        </div>
      )}

      {stockAssets.length > 0 && (
        <div className="flex flex-col gap-4">
          <h2 className="text-white font-bold text-lg">
            Ações{" "}
            <span className="text-nubank-muted text-sm font-normal">
              ({stockAssets.length} ativo{stockAssets.length !== 1 ? "s" : ""})
            </span>
          </h2>
          {stockAssets.map((asset) => (
            <StockCard key={asset.ticker} asset={asset} />
          ))}
        </div>
      )}

      {fiiAssets.length > 0 && (
        <div className="flex flex-col gap-4">
          <h2 className="text-white font-bold text-lg">
            FIIs{" "}
            <span className="text-nubank-muted text-sm font-normal">
              ({fiiAssets.length} fundo{fiiAssets.length !== 1 ? "s" : ""})
            </span>
          </h2>
          {fiiAssets.map((asset) => (
            <FIICard key={asset.ticker} asset={asset} />
          ))}
        </div>
      )}

      {tesourAssets.length > 0 && (
        <div className="flex flex-col gap-4">
          <h2 className="text-white font-bold text-lg">
            Tesouro Direto{" "}
            <span className="text-nubank-muted text-sm font-normal">
              ({tesourAssets.length} posição{tesourAssets.length !== 1 ? "ões" : ""})
            </span>
          </h2>
          {tesourAssets.map((asset) => (
            <TesourCard key={asset.ticker} asset={asset} />
          ))}
        </div>
      )}

      <div className="border-t border-nubank-border pt-6 flex justify-center">
        <button
          type="button"
          onClick={handleNovaAnalise}
          className="px-6 py-3 rounded-xl border border-nubank-border text-nubank-text text-sm font-medium hover:border-nubank-purple hover:text-white transition-colors"
        >
          Analisar outro portfólio
        </button>
      </div>
    </div>
  );
}
