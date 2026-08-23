import os
from huggingface_hub import InferenceClient

HF_TOKEN = os.environ.get("HF_TOKEN") or "your_huggingface_token_here"

models = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "mistralai/Mistral-Nemo-Instruct-2407",
    "microsoft/Phi-3-mini-4k-instruct"
]

for m in models:
    try:
        client = InferenceClient(model=m, token=HF_TOKEN)
        response = client.chat_completion(
            messages=[{"role": "user", "content": "Say 'hello' and nothing else."}],
            max_tokens=10,
            temperature=0.2
        )
        print(f"✅ Success with {m}: {response.choices[0].message.content}")
        break
    except Exception as e:
        print(f"❌ Failed with {m}: {e}")
