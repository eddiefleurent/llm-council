"""FastAPI backend for LLM Council."""

import logging
import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio

logger = logging.getLogger(__name__)

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings, calculate_tournament_rankings
from .context import build_context_messages
from .config import get_council_config, save_council_config, DEFAULT_COUNCIL_MODELS, DEFAULT_CHAIRMAN_MODEL
from .models import get_models_grouped_by_provider, get_models_for_provider, get_available_models, validate_model_ids

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log startup configuration
@app.on_event("startup")
async def startup_event():
    config = get_council_config()
    print("\n" + "="*60)
    print("LLM Council Configuration")
    print("="*60)
    print(f"Council Models ({len(config['council_models'])} members):")
    for i, model in enumerate(config['council_models'], 1):
        print(f"  {i}. {model}")
    print(f"\nChairman Model: {config['chairman_model']}")
    print("="*60 + "\n")


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class UpdateCouncilConfigRequest(BaseModel):
    """Request to update council configuration."""
    council_models: List[str]
    chairman_model: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/debug/config")
async def debug_config():
    """Debug endpoint showing current configuration."""
    config = get_council_config()
    return {
        "council_models": config["council_models"],
        "chairman_model": config["chairman_model"],
        "model_count": len(config["council_models"]),
        "config_file_exists": os.path.exists("data/council_config.json")
    }


# ============================================================================
# Model Discovery Endpoints
# ============================================================================

@app.get("/api/models")
async def list_models():
    """
    Get all available models from OpenRouter, grouped by provider.
    
    Returns providers sorted with priority providers first (OpenAI, Anthropic, etc.),
    with models within each provider sorted by creation date (newest first).
    """
    try:
        return await get_models_grouped_by_provider()
    except Exception as e:
        logger.exception("Failed to fetch models from OpenRouter")
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {str(e)}")


@app.get("/api/models/{provider_id}")
async def list_models_for_provider(provider_id: str):
    """
    Get models for a specific provider.
    
    Args:
        provider_id: Provider identifier (e.g., "anthropic", "openai")
        
    Returns list of models sorted by creation date (newest first).
    """
    try:
        models = await get_models_for_provider(provider_id)
        if not models:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
        return {"provider": provider_id, "models": models}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to fetch models for provider {provider_id}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {str(e)}")


@app.post("/api/models/refresh")
async def refresh_models():
    """
    Force refresh the models cache from OpenRouter.
    
    Useful when new models are added to OpenRouter.
    """
    try:
        from .models import get_available_models
        cache = await get_available_models(force_refresh=True)
        return {"status": "ok", "total_models": len(cache.models)}
    except Exception as e:
        logger.exception("Failed to refresh models cache")
        raise HTTPException(status_code=502, detail=f"Failed to refresh models: {str(e)}")


# ============================================================================
# Council Configuration Endpoints
# ============================================================================

@app.get("/api/council/config")
async def get_council_configuration():
    """
    Get the current council configuration.
    
    Returns the list of council models and the chairman model.
    """
    config = get_council_config()
    return {
        "council_models": config["council_models"],
        "chairman_model": config["chairman_model"],
        "defaults": {
            "council_models": DEFAULT_COUNCIL_MODELS,
            "chairman_model": DEFAULT_CHAIRMAN_MODEL
        }
    }


@app.put("/api/council/config")
async def update_council_configuration(request: UpdateCouncilConfigRequest):
    """
    Update the council configuration.

    Validates that all model IDs exist in OpenRouter before saving.
    """
    # Pre-validation: require council_models and chairman_model
    if not request.council_models:
        raise HTTPException(status_code=400, detail="At least one council model is required")
    if not request.chairman_model:
        raise HTTPException(status_code=400, detail="Chairman model is required")

    # Deduplicate council models while preserving order
    seen = set()
    deduped_council_models = []
    for model_id in request.council_models:
        if model_id not in seen:
            seen.add(model_id)
            deduped_council_models.append(model_id)

    # Lightweight ID format validation helper
    def validate_model_id_format(model_id: str) -> bool:
        """Validate model ID matches 'provider/model' format."""
        return bool(model_id and re.match(r'^[^/]+/[^/]+$', model_id))

    # Validate model ID formats before OpenRouter validation
    invalid_formats = []
    for model_id in deduped_council_models:
        if not validate_model_id_format(model_id):
            invalid_formats.append(model_id)
    if not validate_model_id_format(request.chairman_model):
        invalid_formats.append(request.chairman_model)

    if invalid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model ID format (must be 'provider/model'): {', '.join(invalid_formats)}"
        )

    # Validate models exist in OpenRouter
    try:
        cache = await get_available_models()

        # Combine all models to validate
        all_models_to_validate = deduped_council_models + [request.chairman_model]
        _, invalid_models = validate_model_ids(all_models_to_validate, cache)

        if invalid_models:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model(s): {', '.join(invalid_models)}"
            )
    except HTTPException:
        raise
    except Exception as e:
        # If we can't validate (e.g., OpenRouter is down), still apply format validation
        logger.warning(f"Could not validate models against OpenRouter: {e}")

        # Re-check format validation in fallback path
        if invalid_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model ID format (must be 'provider/model'): {', '.join(invalid_formats)}"
            )

    # Save the configuration (use deduplicated list)
    save_council_config(deduped_council_models, request.chairman_model)

    return {
        "status": "ok",
        "council_models": deduped_council_models,
        "chairman_model": request.chairman_model
    }


@app.post("/api/council/config/reset")
async def reset_council_configuration():
    """
    Reset council configuration to defaults.
    """
    save_council_config(DEFAULT_COUNCIL_MODELS, DEFAULT_CHAIRMAN_MODEL)
    return {
        "status": "ok",
        "council_models": DEFAULT_COUNCIL_MODELS,
        "chairman_model": DEFAULT_CHAIRMAN_MODEL
    }


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.delete("/api/conversations")
async def delete_conversations(confirm: bool = False):
    """Delete all conversations from storage. Requires confirm=true query param."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Pass ?confirm=true to delete all conversations"
        )
    storage.delete_all_conversations()
    return {"status": "ok"}


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Build context messages from conversation history
    # Re-fetch conversation to get the user message we just added
    conversation = storage.get_conversation(conversation_id)
    messages = await build_context_messages(
        conversation["messages"][:-1],  # Exclude the user message we just added
        request.content
    )

    # Run the 3-stage council process with context
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(messages)

    # Collect all errors for persistence
    errors = {
        "stage1": metadata.get("errors", [])[:len(stage1_results)] if metadata.get("errors") else [],
        "stage2": metadata.get("errors", [])[len(stage1_results):len(stage1_results)+len(stage2_results)] if metadata.get("errors") else [],
        "stage3": metadata.get("errors", [])[len(stage1_results)+len(stage2_results):] if metadata.get("errors") else []
    }

    # Add assistant message with all stages and errors
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        errors
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Build context messages from conversation history
            # Re-fetch conversation to get the user message we just added
            conv = storage.get_conversation(conversation_id)
            messages = await build_context_messages(
                conv["messages"][:-1],  # Exclude the user message we just added
                request.content
            )

            # Stage 1: Collect responses with context
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results, stage1_errors = await stage1_collect_responses(messages)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results, 'errors': stage1_errors if stage1_errors else None})}\n\n"

            # Short-circuit if no successful stage1 results (mirrors run_full_council behavior)
            if not stage1_results:
                # Cancel title task if running
                if title_task:
                    title_task.cancel()
                yield f"data: {json.dumps({'type': 'error', 'message': 'All models failed to respond. Please try again.', 'errors': stage1_errors if stage1_errors else None})}\n\n"
                return

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model, stage2_errors = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            tournament_rankings = calculate_tournament_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings, 'tournament_rankings': tournament_rankings}, 'errors': stage2_errors if stage2_errors else None})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result, stage3_errors = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'errors': stage3_errors if stage3_errors else None})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Collect all errors for persistence
            errors = {
                "stage1": stage1_errors if stage1_errors else [],
                "stage2": stage2_errors if stage2_errors else [],
                "stage3": stage3_errors if stage3_errors else []
            }

            # Save complete assistant message with errors
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result,
                errors
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            logger.exception("Error in streaming council process")
            # Send sanitized error event (don't leak internal details)
            yield f"data: {json.dumps({'type': 'error', 'message': 'An unexpected error occurred. Please try again.'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
