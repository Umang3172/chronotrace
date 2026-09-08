"""Check that a Bedrock run will work before spending an eval on finding out.

Every failure here is one that otherwise shows up partway through a benchmark
run: no credentials, a region with no Nova, or an IAM policy that denies
`bedrock:InvokeModel`. Run it first.

There is no model-access step to forget any more. The Bedrock console's model
access page has been retired: serverless foundation models enable themselves on
first invocation in every commercial region, so for Amazon Nova the first
`converse` call *is* the enablement. A denial here is therefore a real IAM or
SCP denial, not a missing opt-in -- which is worth saying, because the old
advice sent people to a console page that no longer exists.

    uv run python scripts/bedrock_preflight.py
"""

from __future__ import annotations

import os
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
    bearer = bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))
    credentials = session.get_credentials()
    if bearer:
        # A Bedrock API key signs bedrock-runtime only. It populates no SigV4
        # credential chain and cannot call STS, so both checks below would
        # report a failure that does not exist.
        print("creds    : AWS_BEARER_TOKEN_BEDROCK (Bedrock API key)")
    elif credentials is None:
        print("\nFAIL  no AWS credentials found.")
        print("      Either export AWS_BEARER_TOKEN_BEDROCK with a Bedrock API key,")
        print("      or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, or write")
        print("      ~/.aws/credentials. Then re-run.")
        return 1
    else:
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
        reason = "a Bedrock API key signs runtime calls only" if bearer else str(exc)
        print(f"\nnote     : could not list models ({reason}); invoking anyway.")
        listed = set()

    for wanted in WANTED:
        if wanted in listed:
            state = "available"
        elif listed:
            state = "NOT LISTED in this region"
        else:
            state = "not checked"
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
        print("\n      Amazon Nova needs no access request: serverless models enable on")
        print("      first invocation. So AccessDenied here is an IAM policy or an SCP")
        print("      denying bedrock:InvokeModel, and ValidationException usually means")
        print("      the model id is not served in this region -- try us-east-1.")
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
