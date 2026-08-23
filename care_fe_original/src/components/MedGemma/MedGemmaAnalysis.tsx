/**
 * MedGemma AI Patient Report Analysis Page.
 *
 * Allows doctors to submit patient data for AI-powered clinical analysis
 * using presets: Comprehensive, Summary, Critical, Timeline.
 */

import { useState } from "react";

import type {
  AnalysisType,
  MedGemmaAnalysisRequest,
  MedGemmaAnalysisResult,
  Preset,
} from "./api";
import { PRESET_CONFIGS, submitAnalysis } from "./api";
import MedGemmaResults from "./MedGemmaResults";

export default function MedGemmaAnalysis() {
  const [selectedPreset, setSelectedPreset] = useState<Preset>("comprehensive");
  const [analysisType, setAnalysisType] =
    useState<AnalysisType>("comprehensive");
  const [patientId, setPatientId] = useState("");
  const [encounterIdInput, setEnounterIdInput] = useState("");
  const [customData, setCustomData] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MedGemmaAnalysisResult | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleAnalyze = async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      // Build input_data
      const inputData: Record<string, unknown> = {};

      // Parse custom JSON data if provided
      if (customData.trim()) {
        try {
          const parsed = JSON.parse(customData);
          Object.assign(inputData, parsed);
        } catch {
          setError(
            "Invalid JSON in custom data field. Please check the format.",
          );
          setIsLoading(false);
          return;
        }
      }

      const request: MedGemmaAnalysisRequest = {
        analysis_type: analysisType,
        input_data: inputData,
        preset: selectedPreset,
        encounter_id: encounterIdInput.trim() || undefined,
        patient_id: patientId.trim() || undefined,
      };

      const analysisResult = await submitAnalysis(request);
      setResult(analysisResult);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Analysis failed. Try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handlePresetSelect = (preset: Preset) => {
    setSelectedPreset(preset);
    setAnalysisType(preset);
  };

  const analysisTypes: { value: AnalysisType; label: string }[] = [
    { value: "comprehensive", label: "Comprehensive Analysis" },
    { value: "summary", label: "Clinical Summary" },
    { value: "critical", label: "Critical Flags & Alerts" },
    { value: "timeline", label: "Medical Timeline" },
    { value: "report_summary", label: "Report Summary" },
    { value: "trend_analysis", label: "Trend Analysis" },
    { value: "ddi_check", label: "Drug Interaction Check" },
    { value: "differential_diagnosis", label: "Differential Diagnosis" },
    { value: "soap_autofill", label: "SOAP Note Autofill" },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            MedGemma
          </span>
          <span className="text-gray-400 font-normal">AI Analysis</span>
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          AI-powered clinical analysis engine. All processing happens on local
          servers — no cloud data egress.
        </p>
      </div>

      {/* Preset Cards */}
      <div>
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
          Select Analysis Type
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {PRESET_CONFIGS.map((preset) => (
            <button
              key={preset.key}
              onClick={() => handlePresetSelect(preset.key)}
              disabled={isLoading}
              className={`relative text-left p-4 rounded-xl border-2 transition-all duration-200 ${
                selectedPreset === preset.key
                  ? "border-indigo-500 bg-indigo-50 shadow-md shadow-indigo-100"
                  : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm"
              } ${isLoading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            >
              {selectedPreset === preset.key && (
                <div className="absolute top-2 right-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500 text-white text-xs">
                    ✓
                  </span>
                </div>
              )}
              <div className="text-2xl mb-2">{preset.icon}</div>
              <div className="font-semibold text-gray-900 text-sm">
                {preset.label}
              </div>
              <p className="text-xs text-gray-500 mt-1 line-clamp-3">
                {preset.description}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Input Section */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-4">
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
          Patient Context
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="medgemma-patient-id"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              ABHA ID
              <span className="text-gray-400 font-normal ml-1">(or Patient UUID)</span>
            </label>
            <input
              id="medgemma-patient-id"
              type="text"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              placeholder="91-1234-5678-9012"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              disabled={isLoading}
            />
            <p className="text-xs text-gray-400 mt-1">
              The system will pull all patient reports from MinIO for analysis
            </p>
          </div>

          <div>
            <label
              htmlFor="medgemma-encounter-id"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Encounter ID{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              id="medgemma-encounter-id"
              type="text"
              value={encounterIdInput}
              onChange={(e) => setEnounterIdInput(e.target.value)}
              placeholder="Link to clinical encounter"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              disabled={isLoading}
            />
          </div>
        </div>

        {/* Advanced Options */}
        <div>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1"
          >
            <span>{showAdvanced ? "▼" : "▶"}</span>
            Advanced Options
          </button>

          {showAdvanced && (
            <div className="mt-3 space-y-3">
              <div>
                <label
                  htmlFor="medgemma-analysis-type"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Analysis Type Override
                </label>
                <select
                  id="medgemma-analysis-type"
                  value={analysisType}
                  onChange={(e) =>
                    setAnalysisType(e.target.value as AnalysisType)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                  disabled={isLoading}
                >
                  {analysisTypes.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="medgemma-custom-data"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Custom Patient Data (JSON)
                </label>
                <textarea
                  id="medgemma-custom-data"
                  value={customData}
                  onChange={(e) => setCustomData(e.target.value)}
                  placeholder={`{\n  "patient": { "name": "...", "age": 28 },\n  "vitals": { "bp": "128/84 mmHg" },\n  "lab_reports": { ... }\n}`}
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  disabled={isLoading}
                />
              </div>
            </div>
          )}
        </div>

        {/* Analyze Button */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleAnalyze}
            disabled={isLoading}
            className={`px-6 py-2.5 rounded-lg text-sm font-semibold text-white transition-all duration-200 ${
              isLoading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-md hover:shadow-lg"
            }`}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
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
                Analyzing patient reports...
              </span>
            ) : (
              "🔬 Run Analysis"
            )}
          </button>

          {result && (
            <button
              onClick={() => setResult(null)}
              className="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
            >
              Clear Results
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center gap-2">
            <span className="text-red-500">❌</span>
            <p className="text-sm text-red-700 font-medium">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && <MedGemmaResults result={result} />}
    </div>
  );
}
