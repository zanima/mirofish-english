"""
Model management API — list, select, and test LLM models at runtime.
"""

from flask import request, jsonify
from openai import OpenAI

from . import models_bp
from ..services.model_registry import ModelRegistry, ModelSelection, PROVIDER_CATALOG, STEP_NAMES
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.models')


@models_bp.route('/available', methods=['GET'])
def get_available_models():
    """Return all providers with their models and the current active selection."""
    registry = ModelRegistry()
    providers = registry.list_providers()
    active = registry.get_active()

    return jsonify({
        "success": True,
        "data": {
            "providers": providers,
            "active": active.to_dict(),
        }
    })


@models_bp.route('/active', methods=['GET'])
def get_active_model():
    """Return the current active model."""
    registry = ModelRegistry()
    active = registry.get_active()
    return jsonify({"success": True, "data": active.to_dict()})


@models_bp.route('/active', methods=['POST'])
def set_active_model():
    """Set the active model for all subsequent LLM calls."""
    body = request.get_json(force=True)
    provider_id = body.get("provider_id")
    model_name = body.get("model_name")

    if not provider_id or not model_name:
        return jsonify({"success": False, "error": "provider_id and model_name are required"}), 400

    registry = ModelRegistry()

    # Resolve base_url and api_key from the catalog
    base_url = body.get("base_url") or registry.get_base_url_for_provider(provider_id)
    api_key = body.get("api_key") or registry.get_api_key_for_provider(provider_id)

    if not base_url:
        return jsonify({"success": False, "error": f"Unknown provider: {provider_id}"}), 400
    if not api_key:
        return jsonify({
            "success": False,
            "error": f"No API key configured for {provider_id}. Set the env var in .env."
        }), 400

    selection = ModelSelection(
        provider_id=provider_id,
        model_name=model_name,
        base_url=base_url,
        api_key=api_key,
    )
    registry.set_active(selection)

    return jsonify({"success": True, "data": selection.to_dict()})


@models_bp.route('/test', methods=['POST'])
def test_model():
    """Send a tiny prompt to the specified model and return success/latency."""
    body = request.get_json(force=True)
    provider_id = body.get("provider_id")
    model_name = body.get("model_name")

    if not provider_id or not model_name:
        return jsonify({"success": False, "error": "provider_id and model_name are required"}), 400

    registry = ModelRegistry()
    base_url = body.get("base_url") or registry.get_base_url_for_provider(provider_id)
    api_key = body.get("api_key") or registry.get_api_key_for_provider(provider_id)

    if not base_url or not api_key:
        return jsonify({"success": False, "error": "Cannot resolve base_url or api_key"}), 400

    try:
        import time
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=30)
        t0 = time.time()
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
            temperature=0,
        )
        latency_ms = int((time.time() - t0) * 1000)
        content = (resp.choices[0].message.content or "").strip()
        return jsonify({
            "success": True,
            "data": {
                "status": "ok",
                "response": content,
                "latency_ms": latency_ms,
            }
        })
    except Exception as exc:
        logger.warning("Model test failed for %s/%s: %s", provider_id, model_name, exc)
        return jsonify({
            "success": True,
            "data": {
                "status": "error",
                "error": str(exc),
            }
        })


@models_bp.route('/steps', methods=['GET'])
def get_step_overrides():
    """Return current per-step model overrides."""
    registry = ModelRegistry()
    overrides = registry.get_step_overrides()
    active = registry.get_active()
    result = {}
    for step in STEP_NAMES:
        if step in overrides:
            result[step] = overrides[step].to_dict()
        else:
            result[step] = None  # uses global active
    return jsonify({
        "success": True,
        "data": {
            "step_overrides": result,
            "global_active": active.to_dict(),
            "steps": STEP_NAMES,
        }
    })


@models_bp.route('/steps/<step>', methods=['POST'])
def set_step_override(step):
    """Set a per-step model override."""
    if step not in STEP_NAMES:
        return jsonify({"success": False, "error": f"Unknown step: {step}. Valid: {STEP_NAMES}"}), 400

    body = request.get_json(force=True)
    provider_id = body.get("provider_id")
    model_name = body.get("model_name")
    if not provider_id or not model_name:
        return jsonify({"success": False, "error": "provider_id and model_name required"}), 400

    registry = ModelRegistry()
    base_url = body.get("base_url") or registry.get_base_url_for_provider(provider_id)
    api_key = body.get("api_key") or registry.get_api_key_for_provider(provider_id)
    if not base_url or not api_key:
        return jsonify({"success": False, "error": "Cannot resolve base_url or api_key"}), 400

    selection = ModelSelection(provider_id=provider_id, model_name=model_name, base_url=base_url, api_key=api_key)
    registry.set_step_override(step, selection)
    return jsonify({"success": True, "data": {"step": step, **selection.to_dict()}})


@models_bp.route('/steps/<step>', methods=['DELETE'])
def clear_step_override(step):
    """Clear a per-step model override (reverts to global active)."""
    if step not in STEP_NAMES:
        return jsonify({"success": False, "error": f"Unknown step: {step}"}), 400
    ModelRegistry().clear_step_override(step)
    return jsonify({"success": True, "message": f"Step '{step}' override cleared"})


@models_bp.route('/estimate', methods=['POST'])
def estimate_cost():
    """Estimate token cost for a model."""
    body = request.get_json(force=True)
    model_name = body.get("model_name", "")
    provider_id = body.get("provider_id", "")
    input_tokens = body.get("input_tokens", 50000)
    output_tokens = body.get("output_tokens", 20000)
    result = ModelRegistry.estimate_cost(model_name, provider_id, input_tokens, output_tokens)
    return jsonify({"success": True, "data": result})


@models_bp.route('/stats', methods=['GET'])
def get_model_stats():
    """Return accumulated usage statistics for all models (latency, token counts)."""
    registry = ModelRegistry()
    stats = registry.get_stats()
    return jsonify({"success": True, "data": stats})
