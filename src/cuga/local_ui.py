"""
Single-process local UI for CUGAr-SALES using Streamlit.
Combines agent orchestration + UI in one process - no separate backend needed.

Usage:
    uv run streamlit run src/cuga/local_ui.py
    # or
    cuga local ui
"""

import streamlit as st
import json
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Import modular components (no FastAPI needed)
from cuga.modular.agents import (
    CoordinatorAgent, 
    PlannerAgent, 
    WorkerAgent, 
    build_default_registry
)
from cuga.modular.config import AgentConfig
from cuga.modular.memory import VectorMemory
from cuga.modular.rag import RagLoader, RagRetriever

# Import LLM client
from cuga.llm import get_llm_client
from cuga.llm.types import ChatMessage
import os


class LLMAdapter:
    """Adapter to make the LLM client compatible with modular agent interface."""
    def __init__(self, client):
        self.client = client
    
    def generate(self, prompt: str, temperature: float = 0.0, max_tokens: int = 500) -> str:
        """Generate response using the LLM client."""
        try:
            # Use ChatMessage dataclass for proper formatting
            messages = [ChatMessage(role="user", content=prompt)]
            response = self.client.chat(messages, temperature=temperature)
            
            # Handle different response types
            if hasattr(response, 'content'):
                return response.content
            elif isinstance(response, str):
                return response
            else:
                return str(response)
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            return f"Error generating response: {str(e)}\n\nDetails: {error_detail}"


# Configure Streamlit page
st.set_page_config(
    page_title="CUGAr-SALES Local",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "profile" not in st.session_state:
    st.session_state.profile = "default"
if "backend" not in st.session_state:
    st.session_state.backend = "local"
if "memory" not in st.session_state:
    st.session_state.memory = VectorMemory(backend_name="local", profile="default")
if "llm_client" not in st.session_state:
    # Initialize LLM from environment configuration
    try:
        llm_client = get_llm_client()
        llm_adapter = LLMAdapter(llm_client)
        model_name = os.getenv('MODEL_NAME', 'default')
        st.session_state.llm_client = llm_adapter
        st.session_state.llm_wrapper = llm_adapter  # Add this for fallback
        st.session_state.llm_model = model_name
        st.session_state.llm_status = f"✅ Connected: {model_name}"
    except Exception as e:
        st.session_state.llm_client = None
        st.session_state.llm_wrapper = None  # Add this for fallback
        st.session_state.llm_model = "none"
        st.session_state.llm_status = f"❌ Error: {e}"

if "coordinator" not in st.session_state:
    registry = build_default_registry()
    config = AgentConfig.from_env()
    
    planner = PlannerAgent(
        registry=registry, 
        memory=st.session_state.memory, 
        config=config,
        llm=st.session_state.llm_client
    )
    worker = WorkerAgent(
        registry=registry, 
        memory=st.session_state.memory
    )
    st.session_state.coordinator = CoordinatorAgent(
        planner=planner, 
        workers=[worker], 
        memory=st.session_state.memory
    )

# Sidebar
with st.sidebar:
    st.title("🎯 CUGAr-SALES")
    st.caption("Local Single-Process Mode")
    
    # LLM Status
    if "llm_status" in st.session_state:
        if "✅" in st.session_state.llm_status:
            st.success(st.session_state.llm_status)
        else:
            st.error(st.session_state.llm_status)
    
    st.divider()
    
    # Profile selector
    profile = st.selectbox(
        "Profile",
        ["default", "enterprise", "smb", "technical"],
        index=["default", "enterprise", "smb", "technical"].index(st.session_state.profile),
        help="Sales profile for tool filtering and budgets"
    )
    
    if profile != st.session_state.profile:
        st.session_state.profile = profile
        # Reinitialize memory with new profile
        st.session_state.memory = VectorMemory(
            backend_name=st.session_state.backend, 
            profile=profile
        )
        st.rerun()
    
    # Memory backend
    backend = st.selectbox(
        "Memory Backend",
        ["local", "chroma", "qdrant", "faiss"],
        index=["local", "chroma", "qdrant", "faiss"].index(st.session_state.backend),
        help="Vector store for RAG memory"
    )
    
    if backend != st.session_state.backend:
        st.session_state.backend = backend
        st.session_state.memory = VectorMemory(backend_name=backend, profile=profile)
        st.rerun()
    
    st.divider()
    
    # Knowledge management
    st.subheader("📚 Knowledge Base")
    uploaded_files = st.file_uploader(
        "Upload documents",
        accept_multiple_files=True,
        type=["txt", "md", "pdf", "json"],
        help="Add files to agent memory"
    )
    
    if uploaded_files:
        if st.button("Ingest Files", type="primary"):
            with st.spinner("Processing files..."):
                try:
                    loader = RagLoader(backend=backend, profile=profile)
                    temp_dir = Path("/tmp/cuga_upload")
                    temp_dir.mkdir(exist_ok=True)
                    
                    file_paths = []
                    for uploaded_file in uploaded_files:
                        file_path = temp_dir / uploaded_file.name
                        file_path.write_bytes(uploaded_file.read())
                        file_paths.append(file_path)
                    
                    added = loader.ingest(file_paths)
                    st.session_state.memory = loader.memory
                    st.success(f"✅ Ingested {added} chunks from {len(uploaded_files)} files")
                except Exception as e:
                    st.error(f"❌ Error ingesting files: {str(e)}")
    
    # Memory stats
    if hasattr(st.session_state.memory, 'store'):
        st.metric("Memory Items", len(st.session_state.memory.store))
    
    st.divider()
    
    # Quick actions
    st.subheader("⚡ Quick Actions")
    if st.button("🔍 Find Chicago Leads"):
        st.session_state.messages.append({
            "role": "user",
            "content": "Find high-value sales leads in Chicago"
        })
        st.rerun()
    
    if st.button("📊 Territory Analysis"):
        st.session_state.messages.append({
            "role": "user", 
            "content": "Analyze my current territory coverage and suggest optimizations"
        })
        st.rerun()
    
    if st.button("✉️ Draft Outreach"):
        st.session_state.messages.append({
            "role": "user",
            "content": "Draft a personalized outreach email for a SaaS company in healthcare"
        })
        st.rerun()
    
    if st.button("🧪 Run Demo"):
        st.session_state.messages.append({
            "role": "user",
            "content": "What sales tools are available?"
        })
        st.rerun()
    
    st.divider()
    
    if st.button("🗑️ Clear History"):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    
    # Mode switcher hint
    with st.expander("💡 About Local Mode"):
        st.markdown("""
        **Local Mode** runs everything in one process:
        - ✅ No separate backend needed
        - ✅ Single command to start
        - ✅ Perfect for demos and learning
        
        For production use with teams:
        - 🏢 Use `./scripts/start-dev.sh`
        - 🏢 Separate FastAPI + React
        - 🏢 WebSocket streaming
        
        See `docs/LOCAL_MODE.md` for details.
        """)

# Main chat interface
st.title("💬 Sales Assistant Chat")
st.caption("Ask me anything about sales operations, territory planning, or lead generation")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Show execution details for assistant messages
        if message["role"] == "assistant" and "trace" in message:
            with st.expander("🔍 Execution Details"):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Trace ID", message.get("trace_id", "N/A")[:8])
                with col2:
                    trace_data = message.get("trace", {})
                    if isinstance(trace_data, dict):
                        steps = trace_data.get("steps", [])
                        st.metric("Steps", len(steps) if isinstance(steps, list) else 0)
                    else:
                        st.metric("Steps", "N/A")
                
                st.json(message["trace"])

# Chat input
if prompt := st.chat_input("What would you like help with?"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Execute agent
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        trace_placeholder = st.empty()
        
        with st.spinner("Thinking..."):
            trace_id = str(uuid.uuid4())
            
            try:
                # Execute coordinator
                result = st.session_state.coordinator.dispatch(prompt, trace_id=trace_id)
                
                # Debug: Check what we got
                response_text = result.output if result and hasattr(result, 'output') else None
                
                # Handle case where no steps were generated (conversational query)
                if not response_text or str(response_text).strip() in ["", "None", "null"]:
                    # Fall back to direct LLM query for conversational responses
                    if st.session_state.llm_wrapper:
                        try:
                            system_prompt = """You are CUGAr-SALES, an AI sales assistant. You help with:
- Sales operations and territory planning
- Lead generation and prospecting  
- Account research and intelligence
- Email drafting and outreach
- BANT/MEDDIC qualification
- Pipeline analysis

You have 10 data adapters (Salesforce, ZoomInfo, Clearbit, HubSpot, 6sense, Apollo, Pipedrive, Crunchbase, BuiltWith, IBM Sales Cloud) and can orchestrate multi-step workflows.

Be helpful and professional."""
                            
                            llm_response = st.session_state.llm_wrapper.generate(
                                prompt=f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:",
                                max_tokens=500
                            )
                            response_text = llm_response
                        except Exception as llm_error:
                            response_text = f"LLM Error: {llm_error}"
                    else:
                        response_text = "⚠️ No LLM configured. Please check your .env file."
                
                # Display result
                message_placeholder.markdown(response_text or "❌ No response generated")
                
                # Show execution trace
                with trace_placeholder.expander("🔍 Execution Details"):
                    st.caption(f"Trace ID: {trace_id}")
                    
                    # Handle trace structure safely
                    trace_data = result.trace if hasattr(result, 'trace') else {}
                    if isinstance(trace_data, dict):
                        col1, col2 = st.columns(2)
                        with col1:
                            steps = trace_data.get("steps", [])
                            st.metric("Steps", len(steps) if isinstance(steps, list) else 0)
                        with col2:
                            duration = trace_data.get("duration_ms", "N/A")
                            st.metric("Duration", f"{duration}ms" if duration != "N/A" else "N/A")
                    
                    st.json(trace_data)
                
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text or "No response",
                    "trace": trace_data,
                    "trace_id": trace_id
                })
                
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
                st.exception(e)

# Footer
st.divider()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.caption("🚀 Single-Process Mode")
with col2:
    st.caption("📦 No Backend Required")
with col3:
    st.caption(f"💾 Profile: {profile}")
with col4:
    st.caption(f"🧠 Backend: {backend}")
