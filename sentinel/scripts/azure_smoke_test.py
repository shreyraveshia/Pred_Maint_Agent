"""
Phase 0.2 - Azure smoke test. Run: python scripts/azure_smoke_test.py
Calls BOTH deployments (open + frontier) with a hello prompt.
Uses azure-ai-inference; if your deployment type needs the openai SDK instead,
check the 'Consume' / 'Code' tab of your deployment in Azure AI Foundry for the
exact snippet and adapt call_model() only.
"""
import os, time
from dotenv import load_dotenv
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import UserMessage
from azure.core.credentials import AzureKeyCredential

load_dotenv()


def call_model(prefix: str) -> None:
    endpoint = os.environ[f"AZURE_{prefix}_ENDPOINT"]
    key = os.environ[f"AZURE_{prefix}_KEY"]
    deployment = os.environ[f"AZURE_{prefix}_DEPLOYMENT"]
    client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    t0 = time.time()
    resp = client.complete(model=deployment,
                           messages=[UserMessage(content="Say hello in one short sentence.")],
                           max_tokens=50)
    ms = int((time.time() - t0) * 1000)
    u = resp.usage
    print(f"[{prefix}] {deployment}: {resp.choices[0].message.content!r}")
    print(f"        tokens in/out = {u.prompt_tokens}/{u.completion_tokens}, latency = {ms} ms")


if __name__ == "__main__":
    for p in ("OPEN", "FRONTIER"):
        try:
            call_model(p)
        except Exception as e:
            print(f"[{p}] FAILED: {type(e).__name__}: {e}")
