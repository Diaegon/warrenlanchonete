"use client";

import { useState, useRef, useEffect } from "react";
import type { AssetType, Company } from "@/lib/api";

export interface AssetRowData {
  id: string;
  ticker: string;
  type: AssetType;
  percentage: string;
}

interface AssetRowProps {
  row: AssetRowData;
  onChange: (updated: AssetRowData) => void;
  onRemove: () => void;
  canRemove: boolean;
  companies: Company[];
}

export default function AssetRow({
  row,
  onChange,
  onRemove,
  canRemove,
  companies,
}: AssetRowProps) {
  const [suggestions, setSuggestions] = useState<Company[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleTickerChange(value: string) {
    const upper = value.toUpperCase();
    onChange({ ...row, ticker: upper });

    if (upper.length >= 2) {
      const filtered = companies
        .filter(
          (c) =>
            c.ticker.startsWith(upper) ||
            c.name.toUpperCase().includes(upper)
        )
        .slice(0, 6);
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }

  function handleSuggestionSelect(company: Company) {
    onChange({
      ...row,
      ticker: company.ticker,
      type: company.asset_type,
    });
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function handlePercentageChange(value: string) {
    if (value === "" || /^\d{0,3}(\.\d{0,2})?$/.test(value)) {
      onChange({ ...row, percentage: value });
    }
  }

  return (
    <div className="flex items-center gap-2 sm:gap-3 flex-wrap sm:flex-nowrap">
      <div className="relative flex-1 min-w-[120px]" ref={wrapperRef}>
        <input
          type="text"
          placeholder="Ticker (ex: WEGE3)"
          value={row.ticker}
          onChange={(e) => handleTickerChange(e.target.value)}
          onFocus={() => {
            if (suggestions.length > 0) setShowSuggestions(true);
          }}
          className="w-full rounded-lg px-3 py-2.5 text-sm font-mono uppercase bg-nubank-card border border-nubank-border text-white placeholder:text-nubank-muted placeholder:normal-case focus:outline-none focus:border-nubank-purple transition-colors"
          aria-label="Ticker do ativo"
          autoComplete="off"
          spellCheck={false}
        />
        {showSuggestions && (
          <ul className="absolute z-20 top-full left-0 right-0 mt-1 bg-nubank-card border border-nubank-border rounded-lg overflow-hidden shadow-xl">
            {suggestions.map((c) => (
              <li key={c.ticker}>
                <button
                  type="button"
                  onMouseDown={() => handleSuggestionSelect(c)}
                  className="w-full text-left px-3 py-2 hover:bg-nubank-purple/20 transition-colors flex items-center justify-between gap-2"
                >
                  <span className="font-mono font-semibold text-sm text-white">
                    {c.ticker}
                  </span>
                  <span className="text-nubank-muted text-xs truncate max-w-[140px]">
                    {c.name}
                  </span>
                  <span className="text-nubank-muted text-xs shrink-0">
                    {c.asset_type}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <select
        value={row.type}
        onChange={(e) =>
          onChange({ ...row, type: e.target.value as AssetType })
        }
        className="rounded-lg px-3 py-2.5 text-sm bg-nubank-card border border-nubank-border text-white focus:outline-none focus:border-nubank-purple transition-colors cursor-pointer"
        aria-label="Tipo do ativo"
      >
        <option value="STOCK">STOCK</option>
        <option value="FII">FII</option>
        <option value="TESOURO">TESOURO</option>
      </select>

      <div className="relative w-24">
        <input
          type="number"
          placeholder="0"
          value={row.percentage}
          onChange={(e) => handlePercentageChange(e.target.value)}
          min={0}
          max={100}
          step={0.5}
          className="w-full rounded-lg pl-3 pr-7 py-2.5 text-sm bg-nubank-card border border-nubank-border text-white placeholder:text-nubank-muted focus:outline-none focus:border-nubank-purple transition-colors [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          aria-label="Percentual do ativo"
        />
        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-nubank-muted text-sm pointer-events-none">
          %
        </span>
      </div>

      <button
        type="button"
        onClick={onRemove}
        disabled={!canRemove}
        className="w-9 h-9 flex items-center justify-center rounded-lg border border-nubank-border text-nubank-muted hover:border-red-500/50 hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0"
        aria-label="Remover ativo"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M1 1L13 13M13 1L1 13"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
