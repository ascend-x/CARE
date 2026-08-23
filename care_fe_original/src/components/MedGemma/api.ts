/**
 * MedGemma AI Analysis API utilities.
 * Types and API calls for the MedGemma patient report analysis endpoint.
 */

import careConfig from "@careConfig";

// ─── Types ───────────────────────────────────────────────────────

export type AnalysisType =
  | "report_summary"
  | "trend_analysis"
  | "ddi_check"
  | "differential_diagnosis"
  | "soap_autofill"
  | "comprehensive"
  | "summary"
  | "critical"
  | "timeline";

export type Preset = "comprehensive" | "summary" | "critical" | "timeline";

export interface KeyFinding {
  parameter: string;
  value: string;
  status: "NORMAL" | "HIGH" | "LOW" | "REVIEW";
  reference: string;
}

export interface TrendDataPoint {
  date: string;
  value: string;
}

export interface Trend {
  parameter: string;
  direction: "INCREASING" | "DECREASING" | "STABLE";
  severity: "CONCERNING" | "IMPROVING" | "STABLE";
  data_points: TrendDataPoint[];
}

export interface DrugInteraction {
  drug_a: string;
  drug_b: string;
  severity: "MILD" | "MODERATE" | "SEVERE";
  mechanism: string;
  recommendation: string;
}

export interface SafeCombination {
  drug_a: string;
  drug_b: string;
  status: string;
}

export interface AllergyAlert {
  allergen: string;
  reaction: string;
  avoid: string[];
  safe_alternatives_for_diabetes?: string[];
}

export interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface Differential {
  condition: string;
  probability: "HIGH" | "MODERATE" | "LOW";
  supporting_evidence: string[];
  recommended_tests: string[];
}

export interface MedGemmaAnalysisResult {
  external_id: string;
  encounter: string | null;
  requester_name: string;
  input_bundle: Record<string, unknown>;
  analysis_type: AnalysisType;
  analysis_result: {
    summary: string;
    flags: string[];
    suggested_questions: string[];
    key_findings?: KeyFinding[];
    trends?: Trend[];
    interactions?: DrugInteraction[];
    safe_combinations?: SafeCombination[];
    allergy_alerts?: AllergyAlert[];
    soap?: SOAPNote;
    differentials?: Differential[];
    confidence?: number;
    analysis_type: string;
    preset_used?: string;
    disclaimer: string;
    is_mock: boolean;
    model_version: string;
    processing_time_ms: number;
    request_id: string;
  };
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  model_version: string;
  is_mock: boolean;
  disclaimer: string;
  processing_time_ms: number | null;
  created_date: string;
}

export interface MedGemmaAnalysisRequest {
  analysis_type: AnalysisType;
  input_data?: Record<string, unknown>;
  encounter_id?: string;
  preset?: Preset | "";
  patient_id?: string;
}

// ─── API Functions ───────────────────────────────────────────────

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("care_access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function submitAnalysis(
  request: MedGemmaAnalysisRequest,
): Promise<MedGemmaAnalysisResult> {
  const url = `${careConfig.apiUrl}/api/v1/medgemma/analyze/`;

  const response = await fetch(url, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Analysis request failed (${response.status})`,
    );
  }

  return response.json();
}

export async function listAnalyses(): Promise<{
  results: MedGemmaAnalysisResult[];
  count: number;
}> {
  const url = `${careConfig.apiUrl}/api/v1/medgemma/?limit=20`;

  const response = await fetch(url, {
    method: "GET",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch analyses (${response.status})`);
  }

  return response.json();
}

// ─── Constants ───────────────────────────────────────────────────

export const ANALYSIS_TYPE_LABELS: Record<AnalysisType, string> = {
  report_summary: "Report Summary",
  trend_analysis: "Trend Analysis",
  ddi_check: "Drug Interaction Check",
  differential_diagnosis: "Differential Diagnosis",
  soap_autofill: "SOAP Note Autofill",
  comprehensive: "Comprehensive Analysis",
  summary: "Clinical Summary",
  critical: "Critical Flags",
  timeline: "Medical Timeline",
};

export const PRESET_CONFIGS: {
  key: Preset;
  label: string;
  description: string;
  icon: string;
  color: string;
}[] = [
  {
    key: "comprehensive",
    label: "Comprehensive",
    description:
      "Full clinical analysis with ICD codes, care plan, nutritional protocol, and actionable directives",
    icon: "📋",
    color: "from-blue-500 to-indigo-600",
  },
  {
    key: "summary",
    label: "Quick Summary",
    description:
      "Fast high-level overview: patient profile, active issues, current medications, recent changes",
    icon: "⚡",
    color: "from-emerald-500 to-teal-600",
  },
  {
    key: "critical",
    label: "Critical Alerts",
    description:
      "Red flags, contraindications, drug interactions, and emergency action plan for next 24-48 hours",
    icon: "🚨",
    color: "from-red-500 to-rose-600",
  },
  {
    key: "timeline",
    label: "Timeline",
    description:
      "Chronological medical history extraction from documents with dated events and treatments",
    icon: "📅",
    color: "from-amber-500 to-orange-600",
  },
];
