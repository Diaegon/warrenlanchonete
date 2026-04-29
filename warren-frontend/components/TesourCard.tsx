"use client";

import type { TesourAssetResult } from "@/lib/api";

interface TesourCardProps {
  asset: TesourAssetResult;
}

export default function TesourCard({ asset }: TesourCardProps) {
  return (
    <div className="bg-nubank-card border border-nubank-border rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-white">{asset.ticker}</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded border bg-green-500/20 text-green-400 border-green-500/40">
              Capital seguro
            </span>
          </div>
          <p className="text-nubank-muted text-xs mt-0.5">
            Tesouro Direto · Renda Fixa
          </p>
        </div>
        <div className="text-right">
          <span className="text-nubank-muted text-xs">Peso no portfólio</span>
          <p className="text-white font-bold text-lg">{asset.percentage}%</p>
        </div>
      </div>
      {asset.verdict && (
        <p className="text-nubank-text text-sm leading-relaxed">
          {asset.verdict}
        </p>
      )}
    </div>
  );
}
