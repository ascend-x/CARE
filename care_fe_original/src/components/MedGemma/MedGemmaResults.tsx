/**
 * MedGemma Analysis Results Display Component.
 * Renders structured AI analysis results with key findings, flags, and suggestions.
 */

import { useState } from "react";

import type { MedGemmaAnalysisResult } from "./api";
import { ANALYSIS_TYPE_LABELS } from "./api";

// ─── Sub-components ──────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    HIGH: "bg-red-100 text-red-800 border-red-200",
    LOW: "bg-amber-100 text-amber-800 border-amber-200",
    NORMAL: "bg-green-100 text-green-800 border-green-200",
    REVIEW: "bg-blue-100 text-blue-800 border-blue-200",
    CONCERNING: "bg-red-100 text-red-800 border-red-200",
    IMPROVING: "bg-green-100 text-green-800 border-green-200",
    STABLE: "bg-gray-100 text-gray-800 border-gray-200",
    MILD: "bg-yellow-100 text-yellow-800 border-yellow-200",
    MODERATE: "bg-orange-100 text-orange-800 border-orange-200",
    SEVERE: "bg-red-100 text-red-800 border-red-200",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${colors[status] || "bg-gray-100 text-gray-700 border-gray-200"}`}
    >
      {status}
    </span>
  );
}

function FlagsList({ flags }: { flags: string[] }) {
  if (!flags || flags.length === 0) return null;

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
        🚩 Flags
      </h4>
      <div className="flex flex-wrap gap-2">
        {flags.map((flag, i) => (
          <span
            key={i}
            className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-red-50 text-red-700 border border-red-200"
          >
            {flag.replace(/_/g, " ")}
          </span>
        ))}
      </div>
    </div>
  );
}

function SuggestedQuestions({ questions }: { questions: string[] }) {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
        💡 Suggested Follow-up Questions
      </h4>
      <ul className="space-y-1.5">
        {questions.map((q, i) => (
          <li
            key={i}
            className="flex items-start gap-2 text-sm text-gray-600 pl-1"
          >
            <span className="text-blue-500 mt-0.5 shrink-0">→</span>
            <span>{q}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────

interface MedGemmaResultsProps {
  result: MedGemmaAnalysisResult;
}

export default function MedGemmaResults({ result }: MedGemmaResultsProps) {
  const [activeTab, setActiveTab] = useState<string>("summary");
  const analysis = result.analysis_result;

  const tabs = [
    { id: "summary", label: "Summary" },
    ...(analysis.key_findings && analysis.key_findings.length > 0
      ? [{ id: "findings", label: "Key Findings" }]
      : []),
    ...(analysis.soap ? [{ id: "soap", label: "SOAP Note" }] : []),
    ...(analysis.trends && analysis.trends.length > 0
      ? [{ id: "trends", label: "Trends" }]
      : []),
    ...(analysis.interactions && analysis.interactions.length > 0
      ? [{ id: "interactions", label: "Interactions" }]
      : []),
    ...(analysis.differentials && analysis.differentials.length > 0
      ? [{ id: "differentials", label: "Differentials" }]
      : []),
  ];

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-gray-50 to-white px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {
                ANALYSIS_TYPE_LABELS[
                  result.analysis_type as keyof typeof ANALYSIS_TYPE_LABELS
                ]
              }{" "}
              — Results
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {analysis.model_version} •{" "}
              {analysis.processing_time_ms
                ? `${analysis.processing_time_ms}ms`
                : ""}{" "}
              •{" "}
              {new Date(result.created_date).toLocaleString("en-IN", {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </p>
          </div>
          {typeof analysis.confidence === "number" &&
            analysis.confidence > 0 && (
              <div className="text-right">
                <div className="text-xs text-gray-500 uppercase tracking-wide">
                  Confidence
                </div>
                <div className="text-lg font-bold text-indigo-600">
                  {(analysis.confidence * 100).toFixed(0)}%
                </div>
              </div>
            )}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="px-6 py-2 bg-amber-50 border-b border-amber-200">
        <p className="text-xs text-amber-700 flex items-center gap-1.5">
          <span>⚠️</span>
          <span>{analysis.disclaimer}</span>
        </p>
      </div>

      {/* Tabs */}
      {tabs.length > 1 && (
        <div className="flex border-b border-gray-200 px-6 bg-gray-50">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-indigo-500 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Tab Content */}
      <div className="p-6 space-y-6">
        {/* Summary Tab */}
        {activeTab === "summary" && (
          <div className="space-y-6">
            <div className="prose prose-sm max-w-none">
              <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                {analysis.summary}
              </p>
            </div>
            <FlagsList flags={analysis.flags} />
            <SuggestedQuestions questions={analysis.suggested_questions} />
          </div>
        )}

        {/* Key Findings Tab */}
        {activeTab === "findings" && analysis.key_findings && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Parameter
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Value
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Reference
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {analysis.key_findings.map((finding, i) => (
                  <tr
                    key={i}
                    className={
                      finding.status !== "NORMAL" ? "bg-red-50/30" : ""
                    }
                  >
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {finding.parameter}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 font-mono">
                      {finding.value}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={finding.status} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {finding.reference}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* SOAP Note Tab */}
        {activeTab === "soap" && analysis.soap && (
          <div className="grid gap-4">
            {(
              [
                ["S", "Subjective", analysis.soap.subjective],
                ["O", "Objective", analysis.soap.objective],
                ["A", "Assessment", analysis.soap.assessment],
                ["P", "Plan", analysis.soap.plan],
              ] as [string, string, string][]
            ).map(([letter, title, content]) => (
              <div
                key={letter}
                className="border border-gray-200 rounded-lg overflow-hidden"
              >
                <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b border-gray-200">
                  <span className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-bold">
                    {letter}
                  </span>
                  <span className="font-semibold text-sm text-gray-700">
                    {title}
                  </span>
                </div>
                <div className="p-4">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                    {content}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Trends Tab */}
        {activeTab === "trends" && analysis.trends && (
          <div className="space-y-4">
            {analysis.trends.map((trend, i) => (
              <div
                key={i}
                className="border border-gray-200 rounded-lg p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-gray-800">
                    {trend.parameter}
                  </span>
                  <div className="flex gap-2">
                    <StatusBadge status={trend.severity} />
                    <span className="text-xs text-gray-500">
                      {trend.direction === "INCREASING"
                        ? "📈"
                        : trend.direction === "DECREASING"
                          ? "📉"
                          : "➡️"}{" "}
                      {trend.direction}
                    </span>
                  </div>
                </div>
                <div className="flex gap-3 overflow-x-auto">
                  {trend.data_points.map((dp, j) => (
                    <div
                      key={j}
                      className="flex flex-col items-center text-xs px-3 py-2 bg-gray-50 rounded-lg min-w-fit"
                    >
                      <span className="text-gray-500">{dp.date}</span>
                      <span className="font-mono font-semibold text-gray-800">
                        {dp.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Interactions Tab */}
        {activeTab === "interactions" && analysis.interactions && (
          <div className="space-y-4">
            {analysis.interactions.map((inter, i) => (
              <div
                key={i}
                className="border border-gray-200 rounded-lg p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {inter.drug_a} ↔ {inter.drug_b}
                  </span>
                  <StatusBadge status={inter.severity} />
                </div>
                <p className="text-xs text-gray-600">{inter.mechanism}</p>
                <p className="text-xs text-indigo-600 font-medium">
                  💊 {inter.recommendation}
                </p>
              </div>
            ))}

            {analysis.allergy_alerts &&
              analysis.allergy_alerts.map((alert, i) => (
                <div
                  key={`allergy-${i}`}
                  className="border border-red-200 bg-red-50 rounded-lg p-4 space-y-2"
                >
                  <div className="font-semibold text-red-800 text-sm">
                    ⚠️ Allergy: {alert.allergen}
                  </div>
                  <p className="text-xs text-red-700">
                    Reaction: {alert.reaction}
                  </p>
                  <div className="text-xs text-red-600">
                    <strong>Avoid:</strong> {alert.avoid.join(", ")}
                  </div>
                </div>
              ))}
          </div>
        )}

        {/* Differentials Tab */}
        {activeTab === "differentials" && analysis.differentials && (
          <div className="space-y-3">
            {analysis.differentials.map((diff, i) => (
              <div
                key={i}
                className="border border-gray-200 rounded-lg p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-gray-800">
                    {diff.condition}
                  </span>
                  <StatusBadge
                    status={
                      diff.probability === "HIGH"
                        ? "CONCERNING"
                        : diff.probability === "MODERATE"
                          ? "MODERATE"
                          : "STABLE"
                    }
                  />
                </div>
                <div className="text-xs text-gray-600">
                  <strong>Evidence:</strong>{" "}
                  {diff.supporting_evidence.join(", ")}
                </div>
                <div className="text-xs text-indigo-600">
                  <strong>Tests:</strong> {diff.recommended_tests.join(", ")}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
