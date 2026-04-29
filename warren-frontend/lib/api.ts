const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AssetType = "STOCK" | "FII" | "TESOURO";

export interface PortfolioAssetInput {
  ticker: string;
  type: AssetType;
  percentage: number;
}

export interface PortfolioRequest {
  assets: PortfolioAssetInput[];
}

export interface FinancialMetric {
  year: number;
  value: number | null;
}

export interface Citation {
  quote: string;
  year: number;
  relevance: string;
}

interface BackendCitation {
  passage: string;
  year: number;
  relevance: string;
}

interface BackendFinancialSnapshot {
  roe: number | null;
  margem_liquida: number | null;
  cagr_lucro: number | null;
  divida_ebitda: number | null;
}

interface BackendPortfolioAlert {
  type: string;
  message: string;
}

interface BackendStockAssetResult {
  type: "STOCK";
  ticker: string;
  company_name: string;
  sector: string | null;
  percentage: number;
  score: number;
  verdict: string;
  financials: BackendFinancialSnapshot;
  buffett_verdict: string;
  buffett_citations: BackendCitation[];
  retail_adaptation_note: string;
}

interface BackendFIIAssetResult {
  type: "FII";
  ticker: string;
  percentage: number;
  verdict: string;
}

interface BackendTesouroAssetResult {
  type: "TESOURO";
  ticker: string;
  percentage: number;
  verdict: string;
}

type BackendAssetResult =
  | BackendStockAssetResult
  | BackendFIIAssetResult
  | BackendTesouroAssetResult;

interface BackendPortfolioAnalysisResponse {
  portfolio_grade: string;
  portfolio_summary: string;
  portfolio_alerts: BackendPortfolioAlert[];
  assets: BackendAssetResult[];
}

export interface StockAssetResult {
  asset_type: "STOCK";
  ticker: string;
  company_name: string;
  sector: string;
  percentage: number;
  score: number;
  verdict: string;
  verdict_detail: string;
  roe_history: FinancialMetric[];
  net_margin_history: FinancialMetric[];
  cagr: number | null;
  debt_ebitda: number | null;
  buffett_verdict: string;
  retail_adaptation: string;
  citations: Citation[];
}

export interface FIIAssetResult {
  asset_type: "FII";
  ticker: string;
  percentage: number;
  verdict: string;
}

export interface TesourAssetResult {
  asset_type: "TESOURO";
  ticker: string;
  percentage: number;
  verdict: string;
}

export type AssetResult = StockAssetResult | FIIAssetResult | TesourAssetResult;

export interface PortfolioAnalysisResponse {
  portfolio_grade: string;
  portfolio_summary: string;
  portfolio_alerts: string[];
  assets: AssetResult[];
}

export interface Company {
  ticker: string;
  name: string;
  sector: string;
  segment: string;
  asset_type: AssetType;
}

export interface ApiError {
  detail: string | { msg: string; loc: string[] }[];
}

function metricFromSnapshot(year: number, value: number | null | undefined): FinancialMetric[] {
  return [{ year, value: value ?? null }];
}

function normalizeAsset(asset: BackendAssetResult): AssetResult {
  if (asset.type === "STOCK") {
    const year = 2024;
    return {
      asset_type: "STOCK",
      ticker: asset.ticker,
      company_name: asset.company_name,
      sector: asset.sector ?? "",
      percentage: asset.percentage,
      score: asset.score,
      verdict: asset.verdict,
      verdict_detail: "",
      roe_history: metricFromSnapshot(year, asset.financials?.roe),
      net_margin_history: metricFromSnapshot(year, asset.financials?.margem_liquida),
      cagr: asset.financials?.cagr_lucro ?? null,
      debt_ebitda: asset.financials?.divida_ebitda ?? null,
      buffett_verdict: asset.buffett_verdict,
      retail_adaptation: asset.retail_adaptation_note,
      citations: (asset.buffett_citations ?? []).map((citation) => ({
        quote: citation.passage,
        year: citation.year,
        relevance: citation.relevance,
      })),
    };
  }

  return {
    asset_type: asset.type,
    ticker: asset.ticker,
    percentage: asset.percentage,
    verdict: asset.verdict,
  };
}

function normalizePortfolioResponse(
  response: BackendPortfolioAnalysisResponse
): PortfolioAnalysisResponse {
  return {
    portfolio_grade: response.portfolio_grade,
    portfolio_summary: response.portfolio_summary,
    portfolio_alerts: (response.portfolio_alerts ?? []).map((alert) => alert.message),
    assets: response.assets.map(normalizeAsset),
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = (await res.json().catch(() => ({ detail: res.statusText }))) as ApiError;
    const message =
      typeof body.detail === "string"
        ? body.detail
        : body.detail.map((e) => e.msg).join(", ");
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export async function analyzePortfolio(
  payload: PortfolioRequest
): Promise<PortfolioAnalysisResponse> {
  const res = await fetch(`${BASE_URL}/api/portfolio/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await handleResponse<BackendPortfolioAnalysisResponse>(res);
  return normalizePortfolioResponse(data);
}

export async function getCompanies(): Promise<Company[]> {
  const res = await fetch(`${BASE_URL}/api/companies`, {
    next: { revalidate: 3600 },
  });
  return handleResponse<Company[]>(res);
}

export async function getCompany(ticker: string): Promise<Company> {
  const res = await fetch(`${BASE_URL}/api/companies/${encodeURIComponent(ticker)}`);
  return handleResponse<Company>(res);
}
