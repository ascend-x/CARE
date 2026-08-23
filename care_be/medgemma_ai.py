"""
Real MedGemma AI service using Hugging Face Inference API.
Expects HF_TOKEN environment variable.
"""

import json
import os
import random
import time
import uuid
from huggingface_hub import InferenceClient

HF_TOKEN = os.environ.get("HF_TOKEN")
# Initialize client
client = InferenceClient(model="Qwen/Qwen2.5-72B-Instruct", token=HF_TOKEN) if HF_TOKEN else None

def _query_hf(messages: list) -> str:
    if not HF_TOKEN or not client:
        raise ValueError("HF_TOKEN environment variable is not set")
    
    # We use chat_completion
    response = client.chat_completion(
        messages=messages,
        max_tokens=1024,
        temperature=0.2
    )
    return response.choices[0].message.content


def _extract_json(text: str) -> dict:
    """Attempt to extract and parse JSON from the LLM response."""
    # Find the first '{' and the last '}'
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Fallback structure if parsing fails
    return {
        "summary": "AI response was not in valid JSON format. Raw output: " + text[:200] + "...",
        "flags": ["PARSE_ERROR"],
        "confidence": 0.0
    }


def analyze(analysis_type, input_data):
    """
    Run Real MedGemma analysis using Hugging Face.
    """
    start_time = time.time()
    
    # Prepare clinical context from input bundle
    clinical_context = json.dumps(input_data, indent=2)[:3000] # truncate to avoid token limits
    
    # Build the prompt based on analysis type
    system_prompt = (
        "You are MedGemma, an expert clinical AI assistant. "
        "Analyze the provided patient data and respond ONLY with a valid JSON object matching the requested schema. "
        "Do not include markdown blocks, just the raw JSON."
    )
    
    schemas = {
        "report_summary": '{"summary": "clinical summary text", "flags": ["FLAG1", "FLAG2"], "key_findings": [{"parameter": "string", "value": "string", "status": "HIGH/LOW/NORMAL", "reference": "string"}], "suggested_questions": ["q1", "q2"], "confidence": 0.95}',
        "trend_analysis": '{"summary": "trend summary", "trends": [{"parameter": "string", "direction": "INCREASING/DECREASING", "severity": "CONCERNING/IMPROVING", "data_points": [{"date": "string", "value": "string"}]}], "flags": ["FLAG1"], "suggested_questions": ["q1"], "confidence": 0.90}',
        "ddi_check": '{"summary": "ddi summary", "interactions": [{"drug_a": "string", "drug_b": "string", "severity": "MILD/MODERATE/SEVERE", "mechanism": "string", "recommendation": "string"}], "safe_combinations": [{"drug_a": "string", "drug_b": "string", "status": "SAFE"}], "allergy_alerts": [], "flags": ["FLAG1"], "suggested_questions": ["q1"], "confidence": 0.90}',
        "differential_diagnosis": '{"summary": "dx summary", "differentials": [{"condition": "string", "probability": "HIGH/MODERATE/LOW", "supporting_evidence": ["ev1"], "recommended_tests": ["test1"]}], "flags": ["FLAG1"], "suggested_questions": ["q1"], "confidence": 0.85}',
        "soap_autofill": '{"summary": "soap summary", "soap": {"subjective": "text", "objective": "text", "assessment": "text", "plan": "text"}, "flags": ["FLAG1"], "suggested_questions": [], "confidence": 0.95}',
        "comprehensive": '{"summary": "comprehensive summary", "flags": ["FLAG1"], "key_findings": [], "suggested_questions": [], "confidence": 0.95}'
    }
    
    schema = schemas.get(analysis_type, schemas["report_summary"])
    
    messages = [
        {"role": "system", "content": f"{system_prompt}\nTarget JSON schema:\n{schema}"},
        {"role": "user", "content": f"Analyze this clinical data for {analysis_type}:\n{clinical_context}"}
    ]
    
    try:
        if HF_TOKEN:
            llm_output = _query_hf(messages)
            result = _extract_json(llm_output)
            is_mock = False
        else:
            # Fallback to mock if token is missing
            raise Exception("HF_TOKEN missing")
            
    except Exception as e:
        print(f"AI Inference failed: {e}. Falling back to mock data.")
        # Fallback to empty/mock response
        result = {
            "summary": f"Could not complete AI analysis: {str(e)}",
            "flags": ["AI_ERROR"],
            "key_findings": [],
            "confidence": 0.0
        }
        is_mock = True

    processing_time_ms = int((time.time() - start_time) * 1000)
    
    return {
        **result,
        "analysis_type": analysis_type,
        "disclaimer": "AI-generated suggestion. Verify clinically.",
        "is_mock": is_mock,
        "model_version": "Qwen/Qwen2.5-72B-Instruct",
        "processing_time_ms": processing_time_ms,
        "request_id": str(uuid.uuid4()),
        "documents_analyzed": [],
    }
