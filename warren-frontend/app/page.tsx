"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import AssetRow, { type AssetRowData } from "@/components/AssetRow";
import { analyzePortfolio, getCompanies, type Company } from "@/lib/api";

let rowCounter = 0;
function generateId() {
  return `row-${++rowCounter}`;
}

function createEmptyRow(): AssetRowData {
  return { id: generateId(), ticker: "", type: "STOCK", percentage: "" };
}

const LOADING_MESSAGES = [
  "Consultando o oráculo de Omaha...",
  "Lendo os relatórios anuais na banheira...",
  "Calculando o moat com régua e compasso...",
  "Perguntando pro Charlie Munger...",
  "Checando se tem Coca-Cola no portfólio...",
];

export default function HomePage() {
  const router = useRouter();
  const [rows, setRows] = useState<AssetRowData[]>([
    createEmptyRow(),
    createEmptyRow(),
  ]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState(LOADING_MESSAGES[0] ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCompanies()
      .then(setCompanies)
      .catch(() => {
        // Autocomplete fails silently — analysis still works
      });
  }, []);

  useEffect(() => {
    if (!isSubmitting) return;
    const interval = setInterval(() => {
      setLoadingMessage(
        LOADING_MESSAGES[Math.floor(Math.random() * LOADING_MESSAGES.length)] ?? ""
      );
    }, 2000);
    return () => clearInterval(interval);
  }, [isSubmitting]);

  const totalPercentage = rows.reduce((sum, r) => {
    const val = parseFloat(r.percentage);
    return sum + (isNaN(val) ? 0 : val);
  }, 0);

  const isValid =
    Math.abs(totalPercentage - 100) < 0.01 &&
    rows.every((r) => r.ticker.trim().length > 0 && r.percentage !== "");

  const updateRow = useCallback(
    (id: string, updated: AssetRowData) => {
      setRows((prev) => prev.map((r) => (r.id === id ? updated : r)));
    },
    []
  );

  const removeRow = useCallback((id: string) => {
    setRows((prev) => prev.filter((r) => r.id !== id));
  }, []);

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, createEmptyRow()]);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || isSubmitting) return;

    setError(null);
    setIsSubmitting(true);

    try {
      const result = await analyzePortfolio({
        assets: rows.map((r) => ({
          ticker: r.ticker.trim().toUpperCase(),
          type: r.type,
          percentage: parseFloat(r.percentage),
        })),
      });

      sessionStorage.setItem("warren_report", JSON.stringify(result));
      router.push("/report");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado. Tenta de novo.");
      setIsSubmitting(false);
    }
  }

  const sumColorClass =
    Math.abs(totalPercentage - 100) < 0.01
      ? "text-green-400"
      : totalPercentage > 100
      ? "text-red-400"
      : "text-yellow-400";

  return (
    <div className="flex flex-col gap-10">
      <div className="text-center pt-4">
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white leading-tight">
          Warren Lanchonete
        </h1>
        <p className="text-nubank-muted mt-2 text-base sm:text-lg">
          Seu portfólio analisado com a filosofia de Buffett.{" "}
          <span className="text-nubank-purple font-medium">Sem frescura.</span>
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-nubank-card border border-nubank-border rounded-2xl p-6 flex flex-col gap-6"
        noValidate
      >
        <div className="flex items-center justify-between">
          <h2 className="text-white font-semibold text-lg">Seu portfólio</h2>
          <div className="flex items-center gap-2">
            <span className="text-nubank-muted text-sm">Total:</span>
            <span className={`font-bold text-lg tabular-nums ${sumColorClass}`}>
              {totalPercentage.toFixed(1)}%
            </span>
          </div>
        </div>

        <div className="hidden sm:grid grid-cols-[1fr_120px_96px_36px] gap-2 sm:gap-3 px-0.5">
          <span className="text-nubank-muted text-xs font-medium uppercase tracking-wider">
            Ticker
          </span>
          <span className="text-nubank-muted text-xs font-medium uppercase tracking-wider">
            Tipo
          </span>
          <span className="text-nubank-muted text-xs font-medium uppercase tracking-wider">
            Peso
          </span>
          <span />
        </div>

        <div className="flex flex-col gap-3">
          {rows.map((row) => (
            <AssetRow
              key={row.id}
              row={row}
              onChange={(updated) => updateRow(row.id, updated)}
              onRemove={() => removeRow(row.id)}
              canRemove={rows.length > 1}
              companies={companies}
            />
          ))}
        </div>

        <button
          type="button"
          onClick={addRow}
          className="self-start flex items-center gap-2 text-nubank-purple text-sm font-medium hover:text-white transition-colors py-1"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              d="M8 1V15M1 8H15"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          Adicionar ativo
        </button>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {!isValid && rows.some((r) => r.ticker || r.percentage) && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-4 py-3">
            <p className="text-yellow-400 text-sm">
              {Math.abs(totalPercentage - 100) >= 0.01
                ? `Os percentuais precisam somar 100%. Faltam ${(
                    100 - totalPercentage
                  ).toFixed(1)}%`
                : "Preencha todos os tickers e percentuais."}
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={!isValid || isSubmitting}
          className="w-full rounded-xl py-3.5 bg-nubank-purple text-white font-bold text-base hover:bg-purple-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-nubank-purple focus-visible:outline-offset-2"
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center gap-3">
              <svg
                className="animate-spin h-4 w-4 shrink-0"
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
              {loadingMessage}
            </span>
          ) : (
            "Analisar portfólio"
          )}
        </button>
      </form>

      <div className="border-t border-nubank-border pt-6">
        <h3 className="text-nubank-muted text-sm font-semibold uppercase tracking-wider mb-3">
          Como funciona
        </h3>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            {
              step: "1",
              title: "Monte seu portfólio",
              desc: "Adicione seus ativos com o peso de cada um. Tem que somar 100%.",
            },
            {
              step: "2",
              title: "A IA analisa tudo",
              desc: "Usamos dados reais e a filosofia do Buffett pra avaliar cada ativo.",
            },
            {
              step: "3",
              title: "Receba o veredicto",
              desc: "Nota geral, alertas irônicos e a visão do oráculo sobre cada papel.",
            },
          ].map(({ step, title, desc }) => (
            <div
              key={step}
              className="bg-nubank-card/50 border border-nubank-border rounded-xl px-4 py-4 flex gap-3"
            >
              <span className="w-7 h-7 rounded-full bg-nubank-purple/20 text-nubank-purple text-sm font-bold flex items-center justify-center shrink-0">
                {step}
              </span>
              <div>
                <p className="text-white text-sm font-semibold">{title}</p>
                <p className="text-nubank-muted text-xs mt-0.5 leading-relaxed">
                  {desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
