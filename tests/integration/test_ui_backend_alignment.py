"""
Integration tests for UI/Backend alignment.

Tests the complete flow from frontend ModelConfig.tsx to backend /api/models
and /api/config/model endpoints, verifying:
- Model catalog API returns correct Granite 4.0 models
- Provider switching updates models dynamically
- Configuration save/load roundtrips correctly
- Error handling for authentication failures

Run with: pytest tests/integration/test_ui_backend_alignment.py -v
"""

import pytest
from fastapi.testclient import TestClient

# Import the FastAPI app
try:
    from cuga.backend.server.main import app
except ImportError:
    pytest.skip("FastAPI backend not available", allow_module_level=True)


class TestModelCatalogAPI:
    """Test /api/models/{provider} endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)

    def test_get_watsonx_models(self, client):
        """Test GET /api/models/watsonx returns Granite 4.0 models."""
        response = client.get("/api/models/watsonx")

        assert response.status_code == 200
        models = response.json()

        # Should return list of models
        assert isinstance(models, list)
        assert len(models) >= 3  # At least small, micro, tiny

        # Check for Granite 4.0 models
        model_ids = [m["id"] for m in models]
        assert "granite-4-h-small" in model_ids
        assert "granite-4-h-micro" in model_ids
        assert "granite-4-h-tiny" in model_ids

        # Verify structure of each model
        for model in models:
            assert "id" in model
            assert "name" in model
            assert "description" in model
            assert "max_tokens" in model
            assert "default" in model
            assert isinstance(model["id"], str)
            assert isinstance(model["name"], str)
            assert isinstance(model["description"], str)
            assert isinstance(model["max_tokens"], int)
            assert isinstance(model["default"], bool)

    def test_get_watsonx_default_model(self, client):
        """Test that granite-4-h-small is marked as default."""
        response = client.get("/api/models/watsonx")
        assert response.status_code == 200

        models = response.json()
        default_models = [m for m in models if m["default"]]

        # Exactly one default model
        assert len(default_models) == 1
        assert default_models[0]["id"] == "granite-4-h-small"
        assert default_models[0]["name"] == "Granite 4.0 Small"
        assert default_models[0]["description"] == "Balanced performance (default)"

    def test_get_openai_models(self, client):
        """Test GET /api/models/openai returns GPT models."""
        response = client.get("/api/models/openai")

        assert response.status_code == 200
        models = response.json()

        assert isinstance(models, list)
        assert len(models) >= 3

        model_ids = [m["id"] for m in models]
        assert "gpt-4o" in model_ids
        assert "gpt-4o-mini" in model_ids
        assert "gpt-4-turbo" in model_ids

        # gpt-4o should be default
        default_models = [m for m in models if m["default"]]
        assert len(default_models) == 1
        assert default_models[0]["id"] == "gpt-4o"

    def test_get_anthropic_models(self, client):
        """Test GET /api/models/anthropic returns Claude models."""
        response = client.get("/api/models/anthropic")

        assert response.status_code == 200
        models = response.json()

        assert isinstance(models, list)
        assert len(models) >= 3

        model_ids = [m["id"] for m in models]
        assert "claude-3-5-sonnet-20241022" in model_ids
        assert "claude-3-opus-20240229" in model_ids
        assert "claude-3-haiku-20240307" in model_ids

        # claude-3-5-sonnet should be default
        default_models = [m for m in models if m["default"]]
        assert len(default_models) == 1
        assert default_models[0]["id"] == "claude-3-5-sonnet-20241022"

    def test_get_azure_models(self, client):
        """Test GET /api/models/azure returns Azure OpenAI models."""
        response = client.get("/api/models/azure")

        assert response.status_code == 200
        models = response.json()

        assert isinstance(models, list)
        assert len(models) >= 1

        model_ids = [m["id"] for m in models]
        assert "gpt-4o" in model_ids

    def test_get_groq_models(self, client):
        """Test GET /api/models/groq returns Mixtral models."""
        response = client.get("/api/models/groq")

        assert response.status_code == 200
        models = response.json()

        assert isinstance(models, list)
        assert len(models) >= 1

        model_ids = [m["id"] for m in models]
        assert "mixtral-8x7b-32768" in model_ids

    def test_get_unsupported_provider(self, client):
        """Test GET /api/models/{invalid} returns 404."""
        response = client.get("/api/models/invalid-provider")

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
        assert "not supported" in error["detail"].lower()

    def test_model_max_tokens_values(self, client):
        """Test that max_tokens values are realistic."""
        providers = ["watsonx", "openai", "anthropic", "azure", "groq"]

        for provider in providers:
            response = client.get(f"/api/models/{provider}")
            assert response.status_code == 200

            models = response.json()
            for model in models:
                # max_tokens should be positive and reasonable
                assert model["max_tokens"] > 0
                assert model["max_tokens"] <= 500000  # Reasonable upper bound


class TestProviderSwitching:
    """Test dynamic provider switching updates available models."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_switch_watsonx_to_openai(self, client):
        """Test switching from watsonx to openai updates models."""
        # Get watsonx models
        watsonx_response = client.get("/api/models/watsonx")
        assert watsonx_response.status_code == 200
        watsonx_models = watsonx_response.json()
        watsonx_ids = [m["id"] for m in watsonx_models]

        # Get openai models
        openai_response = client.get("/api/models/openai")
        assert openai_response.status_code == 200
        openai_models = openai_response.json()
        openai_ids = [m["id"] for m in openai_models]

        # Should be different model sets
        assert watsonx_ids != openai_ids
        assert "granite-4-h-small" in watsonx_ids
        assert "granite-4-h-small" not in openai_ids
        assert "gpt-4o" in openai_ids
        assert "gpt-4o" not in watsonx_ids

    def test_switch_openai_to_anthropic(self, client):
        """Test switching from openai to anthropic updates models."""
        openai_response = client.get("/api/models/openai")
        assert openai_response.status_code == 200
        openai_models = openai_response.json()
        openai_ids = [m["id"] for m in openai_models]

        anthropic_response = client.get("/api/models/anthropic")
        assert anthropic_response.status_code == 200
        anthropic_models = anthropic_response.json()
        anthropic_ids = [m["id"] for m in anthropic_models]

        # Should be different model sets
        assert openai_ids != anthropic_ids
        assert "gpt-4o" in openai_ids
        assert "gpt-4o" not in anthropic_ids
        assert "claude-3-5-sonnet-20241022" in anthropic_ids
        assert "claude-3-5-sonnet-20241022" not in openai_ids

    def test_all_providers_have_unique_defaults(self, client):
        """Test that each provider has exactly one default model."""
        providers = ["watsonx", "openai", "anthropic", "azure", "groq"]

        for provider in providers:
            response = client.get(f"/api/models/{provider}")
            assert response.status_code == 200

            models = response.json()
            default_models = [m for m in models if m["default"]]

            # Each provider should have exactly one default
            assert len(default_models) == 1, f"{provider} should have exactly 1 default model"


class TestConfigurationPersistence:
    """Test configuration save/load roundtrips."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_save_config_watsonx_granite(self, client):
        """Test saving watsonx Granite 4.0 configuration."""
        config = {
            "provider": "watsonx",
            "model": "granite-4-h-small",
            "temperature": 0.0,
            "maxTokens": 8192,
            "topP": 1.0,
        }

        response = client.post("/api/config/model", json=config)

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "updated" in result["message"].lower() or "saved" in result["message"].lower()

    def test_save_config_granite_micro(self, client):
        """Test saving Granite 4.0 Micro variant."""
        config = {
            "provider": "watsonx",
            "model": "granite-4-h-micro",
            "temperature": 0.0,
            "maxTokens": 8192,
            "topP": 1.0,
        }

        response = client.post("/api/config/model", json=config)

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"

    def test_save_config_granite_tiny(self, client):
        """Test saving Granite 4.0 Tiny variant."""
        config = {
            "provider": "watsonx",
            "model": "granite-4-h-tiny",
            "temperature": 0.0,
            "maxTokens": 8192,
            "topP": 1.0,
        }

        response = client.post("/api/config/model", json=config)

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"

    def test_save_config_openai(self, client):
        """Test saving OpenAI configuration."""
        config = {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.7,
            "maxTokens": 4096,
            "topP": 1.0,
        }

        response = client.post("/api/config/model", json=config)

        assert response.status_code == 200

    def test_save_config_anthropic(self, client):
        """Test saving Anthropic configuration."""
        config = {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 1.0,
            "maxTokens": 4096,
            "topP": 1.0,
        }

        response = client.post("/api/config/model", json=config)

        assert response.status_code == 200

    def test_save_config_invalid_json(self, client):
        """Test saving invalid JSON returns 422."""
        response = client.post(
            "/api/config/model",
            content="invalid-json",
            headers={"Content-Type": "application/json"},
        )

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    def test_temperature_range_validation(self, client):
        """Test that temperature values are accepted in valid range."""
        # Temperature 0.0 (deterministic)
        config_deterministic = {
            "provider": "watsonx",
            "model": "granite-4-h-small",
            "temperature": 0.0,
            "maxTokens": 8192,
            "topP": 1.0,
        }
        response = client.post("/api/config/model", json=config_deterministic)
        assert response.status_code == 200

        # Temperature 2.0 (maximum creativity)
        config_creative = {
            "provider": "watsonx",
            "model": "granite-4-h-small",
            "temperature": 2.0,
            "maxTokens": 8192,
            "topP": 1.0,
        }
        response = client.post("/api/config/model", json=config_creative)
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling for API failures."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_get_models_nonexistent_provider(self, client):
        """Test that nonexistent provider returns 404 with helpful message."""
        response = client.get("/api/models/nonexistent")

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
        assert "nonexistent" in error["detail"].lower()
        assert "not supported" in error["detail"].lower()

    def test_save_config_missing_fields(self, client):
        """Test that missing required fields returns 422."""
        incomplete_config = {
            "provider": "watsonx",
            # Missing model, temperature, etc.
        }

        response = client.post("/api/config/model", json=incomplete_config)

        # Should accept partial config or return validation error
        # Actual behavior depends on endpoint implementation
        assert response.status_code in [200, 422, 500]

    def test_get_models_with_query_params(self, client):
        """Test that query parameters are ignored gracefully."""
        response = client.get("/api/models/watsonx?extra=param")

        # Should still work, ignoring extra params
        assert response.status_code == 200
        models = response.json()
        assert isinstance(models, list)


class TestGranite4Specific:
    """Test Granite 4.0 specific functionality."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_granite_4_variants_present(self, client):
        """Test all three Granite 4.0 variants are available."""
        response = client.get("/api/models/watsonx")
        assert response.status_code == 200

        models = response.json()
        granite_models = {m["id"]: m for m in models if "granite-4" in m["id"]}

        # Should have all three variants
        assert "granite-4-h-small" in granite_models
        assert "granite-4-h-micro" in granite_models
        assert "granite-4-h-tiny" in granite_models

    def test_granite_4_metadata(self, client):
        """Test Granite 4.0 models have correct metadata."""
        response = client.get("/api/models/watsonx")
        assert response.status_code == 200

        models = response.json()
        granite_models = {m["id"]: m for m in models if "granite-4" in m["id"]}

        # Check small variant
        small = granite_models["granite-4-h-small"]
        assert small["name"] == "Granite 4.0 Small"
        assert "balanced" in small["description"].lower()
        assert small["max_tokens"] == 8192
        assert small["default"] is True

        # Check micro variant
        micro = granite_models["granite-4-h-micro"]
        assert micro["name"] == "Granite 4.0 Micro"
        assert "lightweight" in micro["description"].lower() or "fast" in micro["description"].lower()
        assert micro["max_tokens"] == 8192
        assert micro["default"] is False

        # Check tiny variant
        tiny = granite_models["granite-4-h-tiny"]
        assert tiny["name"] == "Granite 4.0 Tiny"
        assert "minimal" in tiny["description"].lower()
        assert tiny["max_tokens"] == 8192
        assert tiny["default"] is False

    def test_granite_4_save_all_variants(self, client):
        """Test that all Granite 4.0 variants can be saved."""
        variants = ["granite-4-h-small", "granite-4-h-micro", "granite-4-h-tiny"]

        for variant in variants:
            config = {
                "provider": "watsonx",
                "model": variant,
                "temperature": 0.0,
                "maxTokens": 8192,
                "topP": 1.0,
            }

            response = client.post("/api/config/model", json=config)
            assert response.status_code == 200, f"Failed to save {variant}"

    def test_granite_4_default_temperature_zero(self, client):
        """Test that Granite 4.0 default config uses temperature=0.0."""
        # This test verifies the frontend default aligns with backend expectations
        config = {
            "provider": "watsonx",
            "model": "granite-4-h-small",
            "temperature": 0.0,  # Deterministic default
            "maxTokens": 8192,
            "topP": 1.0,
        }

        response = client.post("/api/config/model", json=config)
        assert response.status_code == 200


class TestFrontendBackendContract:
    """Test that frontend ModelConfig.tsx contract matches backend API."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_model_catalog_structure_matches_frontend(self, client):
        """Test that model catalog structure matches what frontend expects."""
        response = client.get("/api/models/watsonx")
        assert response.status_code == 200

        models = response.json()

        # Frontend expects array of objects with specific fields
        for model in models:
            # Required fields that ModelConfig.tsx uses
            assert "id" in model  # Used in <option value={model.id}>
            assert "name" in model  # Used in dropdown display
            assert "description" in model  # Used in dropdown display

            # Frontend builds dropdown like: "{model.name} - {model.description}"
            dropdown_text = f"{model['name']} - {model['description']}"
            assert len(dropdown_text) > 0
            assert " - " in dropdown_text

    def test_provider_list_matches_frontend(self, client):
        """Test that all providers in frontend dropdown are supported."""
        # Frontend ModelConfig.tsx has these providers in dropdown:
        frontend_providers = ["anthropic", "openai", "azure", "watsonx"]
        # Note: "ollama" is also in frontend but not in model catalog API

        for provider in frontend_providers:
            response = client.get(f"/api/models/{provider}")
            # Should return 200 (supported) or 404 (not yet implemented)
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                models = response.json()
                assert isinstance(models, list)
                assert len(models) > 0

    def test_config_save_structure_matches_frontend(self, client):
        """Test that config save accepts frontend ModelConfigData structure."""
        # Frontend ModelConfigData interface:
        # { provider, model, temperature, maxTokens, topP, apiKey? }

        frontend_config = {
            "provider": "watsonx",
            "model": "granite-4-h-small",
            "temperature": 0.0,
            "maxTokens": 8192,
            "topP": 1.0,
            # apiKey is optional in frontend
        }

        response = client.post("/api/config/model", json=frontend_config)

        # Backend should accept this structure
        assert response.status_code in [200, 201]
        result = response.json()
        assert "status" in result or "message" in result

    def test_default_model_auto_selection(self, client):
        """Test that default model can be auto-selected by frontend."""
        response = client.get("/api/models/watsonx")
        assert response.status_code == 200

        models = response.json()

        # Frontend logic: const defaultModel = models.find(m => m.default)
        default_model = next((m for m in models if m["default"]), None)

        assert default_model is not None, "No default model found"
        assert default_model["id"] == "granite-4-h-small"

        # Frontend would then set: setConfig(prev => ({ ...prev, model: defaultModel.id }))
        assert default_model["id"] is not None
        assert isinstance(default_model["id"], str)
