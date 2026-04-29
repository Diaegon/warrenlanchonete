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
  return handleResponse<PortfolioAnalysisResponse>(res);
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
