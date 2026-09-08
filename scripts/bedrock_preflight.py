"""Check that a Bedrock run will work before spending an eval on finding out.

Every failure here is one that otherwise shows up partway through a benchmark
run: no credentials, a region with no Nova, or model access that was never
requested in the console. Run it first.

    uv run python scripts/bedrock_preflight.py
"""

from __future__ import annotations

import sys

from chronotrace.config import get_settings

WANTED = ("amazon.nova-pro-v1:0", "amazon.nova-lite-v1:0")


def main() -> int:
    """Report on credentials, region, model listing and one real invocation."""
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        print("FAIL  boto3 missing. Run: uv sync --extra bedrock")
        return 1

    settings = get_settings()
    region = settings.aws_region
    model_id = settings.model_id_large or "amazon.nova-pro-v1:0"
    print(f"provider : {settings.provider}")
    print(f"region   : {region}   (set CHRONOTRACE_AWS_REGION to change)")
    print(f"model    : {model_id}")

    session = boto3.Session(region_name=region)
    credentials = session.get_credentials()
    if credentials is None:
        print("\nFAIL  no AWS credentials found.")
        print("      export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, or write")
        print("      ~/.aws/credentials, then re-run.")
        return 1
    print(f"creds    : found ({credentials.method})")

    try:
        identity = session.client("sts").get_caller_identity()
        print(f"account  : {identity['Account']}  as {identity['Arn'].split('/')[-1]}")
    except (ClientError, BotoCoreError) as exc:
        print(f"\nFAIL  credentials present but rejected: {exc}")
        return 1

    try:
        listed = {
            summary["modelId"]
            for summary in session.client("bedrock").list_foundation_models()["modelSummaries"]
        }
    except (ClientError, BotoCoreError) as exc:
        print(f"\nWARN  could not list models ({exc}); trying the invocation anyway.")
        listed = set()

    for wanted in WANTED:
        state = "available" if wanted in listed else "NOT LISTED in this region"
        print(f"  {wanted:<28} {state}")

    print(f"\ninvoking {model_id} ...")
    try:
        response = session.client("bedrock-runtime").converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply with the single word: ready"}]}],
            inferenceConfig={"temperature": 0.0, "maxTokens": 16},
        )
    except (ClientError, BotoCoreError) as exc:
        print(f"FAIL  {exc}")
        print("\n      AccessDeniedException usually means model access has not been")
        print("      requested: Bedrock console -> Model access -> enable Amazon Nova.")
        return 1

    usage = response.get("usage", {})
    text = response["output"]["message"]["content"][0].get("text", "").strip()
    print(f"OK    model replied {text!r}")
    print(f"      tokens in {usage.get('inputTokens')}, out {usage.get('outputTokens')}")
    print("\nReady. Next:")
    print("  uv run chronotrace agent --demo")
    print("  uv run chronotrace three-arm --cases all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
