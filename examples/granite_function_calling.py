"""Example showing how to call WatsonxProvider deterministically with Granite 4.0.

Granite 4.0 Models:
    - granite-4-h-small: Balanced performance (default)
    - granite-4-h-micro: Lightweight, fast inference
    - granite-4-h-tiny: Minimal resource usage

Required environment variables:
    - WATSONX_API_KEY
    - WATSONX_PROJECT_ID
    - WATSONX_URL (optional, defaults to IBM Cloud)
"""

from cuga.providers.watsonx_provider import WatsonxProvider

# Uses default model: granite-4-h-small
provider = WatsonxProvider()
print(provider.generate("hello granite", seed=1))

# Or specify a different Granite 4.0 variant
provider_micro = WatsonxProvider(model_id="granite-4-h-micro")
print(provider_micro.generate("hello granite micro", seed=42))
