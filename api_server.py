#!/usr/bin/env python3
"""
FastAPI server for E2B Agent with SSE support
Simple API: POST to /agent/start with prompt, returns SSE stream
"""

import os
import sys
import warnings
import logging

# Suppress Google gRPC ALTS warnings (must be set before importing grpc)
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_TRACE"] = ""
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "ERROR"

# Suppress deprecation warnings in console
warnings.filterwarnings("ignore")

# Redirect stderr for absl/gRPC warnings
import io
_original_stderr = sys.stderr

class FilteredStderr:
    """Filter out specific warning patterns from stderr"""
    def __init__(self, original):
        self.original = original
        
    def write(self, message):
        # Filter out ALTS and absl warnings
        if any(x in message for x in ['ALTS creds', 'absl::InitializeLog', 'E0000']):
            return  # Suppress
        self.original.write(message)
        
    def flush(self):
        self.original.flush()

sys.stderr = FilteredStderr(_original_stderr)

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.e2b_agent import E2BTestOpsAI
from app.firestore import firestore_client
from app.schema import AgentState, Message
from app.webhook import StepExecutionSchema

app = FastAPI(title="E2B Agent API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active sessions
active_sessions = {}

# Store human response queues by session_id
human_response_queues = {}


# Shared function to execute a test case (used by replay and runs)
async def execute_test_case_proven_steps(
    tenant_id: str,
    test_case_id: str,
    run_id: str = None,
    run_updates_callback = None
):
    """
    Execute proven steps from a test case
    
    Args:
        tenant_id: Tenant ID
        test_case_id: Test case ID
        run_id: Optional run ID (for run execution tracking)
        run_updates_callback: Optional async callback(update_dict) for run progress
        
    Returns:
        Dict with execution results
    """
    agent = None
    execution_id = None
    
    try:
        from app.agent.e2b_agent import E2BTestOpsAI
        
        # Generate execution ID
        execution_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_replay"
        
        # Get test case
        doc_ref = firestore_client.db.collection("test_cases").document(test_case_id)
        test_case_doc = doc_ref.get()
        
        if not test_case_doc.exists:
            return {"success": False, "error": "Test case not found"}
        
        test_case_data = test_case_doc.to_dict()
        proven_steps = test_case_data.get("proven_steps", [])
        
        if not proven_steps:
            return {"success": False, "error": "No proven steps found"}
        
        user_id = f"{tenant_id}_replay"
        
        # Callback for run updates
        if run_updates_callback:
            await run_updates_callback({
                f'results.{test_case_id}.status': 'running',
                f'results.{test_case_id}.started_at': datetime.now(timezone.utc).isoformat(),
                f'results.{test_case_id}.total_steps': len(proven_steps)
            })
        
        # Create E2B sandbox
        agent = await E2BTestOpsAI.create(
            session_id=execution_id,
            user_id=user_id,
            tenant_id=tenant_id,
            test_case_id=test_case_id
        )
        
        # Get VNC URL (using wss for WebSocket connection)
        vnc_url = None
        if agent.sandbox and hasattr(agent.sandbox, "sandbox"):
            try:
                host = agent.sandbox.sandbox.get_host(6080)
                vnc_url = f"wss://{host}/websockify"  # Secure WebSocket URL for noVNC
                
                if run_updates_callback:
                    await run_updates_callback({f'results.{test_case_id}.vnc_url': vnc_url})
            except:
                pass
        
        # Execute each proven step
        passed_count = 0
        failed_count = 0
        
        print(f"Executing {len(proven_steps)} proven steps...")
        import time
        execution_start = time.time()
        
        for idx, step in enumerate(proven_steps):
            step_start = time.time()
            step_number = step.get("step_number", idx + 1)
            
            # Handle both formats: {tool_name, arguments} OR {action: {tool_name, arguments}}
            if "action" in step and isinstance(step["action"], dict):
                # New nested format
                tool_name = step["action"].get("tool_name")
                arguments = step["action"].get("arguments", {})
            else:
                # Simple format (preferred)
                tool_name = step.get("tool_name")
                arguments = step.get("arguments", {})
            
            print(f"  Step {step_number}: {tool_name} {arguments.get('action', '')}")
            
            # Update current step
            if run_updates_callback:
                await run_updates_callback({f'results.{test_case_id}.current_step': step_number})
            
            # Execute step
            tool = agent.available_tools.get_tool(tool_name)
            if not tool:
                print(f"  ❌ Tool {tool_name} not found")
                failed_count += 1
                continue
            
            try:
                result = await tool.execute(**arguments)
                has_error = (hasattr(result, 'error') and result.error) or str(result).startswith("Error:")
                
                step_elapsed = time.time() - step_start
                
                if has_error:
                    print(f"  ❌ Failed ({step_elapsed:.2f}s): {str(result)[:100]}")
                    failed_count += 1
                    # Stop on assertion failure
                    if arguments.get('action', '').startswith('assert'):
                        print(f"  ⚠️  Assertion failed - stopping replay")
                        break
                else:
                    print(f"  ✅ Success ({step_elapsed:.2f}s)")
                    passed_count += 1
                    
            except Exception as e:
                print(f"  ❌ Exception: {str(e)}")
                failed_count += 1
                break
        
        total_elapsed = time.time() - execution_start
        print(f"\nTest case complete: {passed_count} passed, {failed_count} failed ({total_elapsed:.2f}s total)")
        
        # Determine final status
        final_status = 'passed' if failed_count == 0 else 'failed'
        
        # Update result
        if run_updates_callback:
            await run_updates_callback({
                f'results.{test_case_id}.status': final_status,
                f'results.{test_case_id}.completed_at': datetime.now(timezone.utc).isoformat(),
                f'results.{test_case_id}.passed_steps': passed_count,
                f'results.{test_case_id}.failed_steps': failed_count
            })
        
        return {
            "success": final_status == 'passed',
            "status": final_status,
            "passed_steps": passed_count,
            "failed_steps": failed_count,
            "total_steps": len(proven_steps)
        }
        
    except Exception as e:
        if run_updates_callback:
            await run_updates_callback({
                f'results.{test_case_id}.status': 'failed',
                f'results.{test_case_id}.error': str(e),
                f'results.{test_case_id}.completed_at': datetime.now(timezone.utc).isoformat()
            })
        return {"success": False, "error": str(e)}
        
    finally:
        # Cleanup sandbox
        if agent:
            await agent.cleanup()
        
        # Clear VNC URL
        if run_updates_callback:
            await run_updates_callback({f'results.{test_case_id}.vnc_url': None})


class AgentRequest(BaseModel):
    prompt: str
    user_id: str  # Firebase UID
    max_steps: Optional[int] = 20
    tenant_id: Optional[str] = None  # Tenant/Organization ID
    test_case_id: Optional[str] = None  # Test Case ID


class RunExecuteRequest(BaseModel):
    run_id: str
    tenant_id: str
    parallel: Optional[bool] = False  # Execute test cases in parallel


@app.post("/agent/create-session")
async def create_session(request: AgentRequest):
    """
    Create a new agent session (non-SSE)

    Returns: session_id immediately without starting execution
    """
    try:
        from datetime import datetime

        session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Create session in Firestore
        await firestore_client.create_session(
            session_id=session_id,
            sandbox_id=None,
            agent_name="E2BTestOpsAI",
            prompt=request.prompt,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            test_case_id=request.test_case_id,
        )

        return {
            "session_id": session_id,
            "user_id": request.user_id,
            "status": "created",
            "message": "Session created. Use /agent/execute/{session_id} to start execution with SSE",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/start")
async def start_agent(request: AgentRequest):
    """
    Start E2B agent and stream execution via SSE

    Returns: Server-Sent Events stream with execution updates
    """

    # Log incoming request parameters
    print(f"\n{'='*70}")
    print(f"📥 INCOMING REQUEST")
    print(f"{'='*70}")
    print(f"User ID: {request.user_id}")
    if request.tenant_id:
        print(f"Tenant ID: {request.tenant_id}")
    if request.test_case_id:
        print(f"Test Case ID: {request.test_case_id}")
    print(f"Max Steps: {request.max_steps or 20}")
    print(f"Prompt:")
    print(f"  {request.prompt}")
    print(f"{'='*70}\n")
    
    async def event_generator():
        """Generate SSE events during agent execution"""
        agent = None
        session_id = None  # Initialize early for error handling

        try:
            # Create a queue for step events
            step_queue = asyncio.Queue()

            # Monkey-patch webhook client BEFORE creating agent
            from app import webhook as webhook_module

            original_send = webhook_module.webhook_client.send_step_data
            original_init = webhook_module.webhook_client.send_sandbox_initializing
            original_ready = webhook_module.webhook_client.send_sandbox_ready

            async def send_and_stream(step_data: StepExecutionSchema):
                # Push to SSE stream FIRST
                await step_queue.put(step_data)
                # Send to webhook
                if webhook_module.webhook_client.enabled:
                    return await original_send(step_data)
                return True

            async def init_and_stream(agent_name: str):
                await step_queue.put(
                    StepExecutionSchema(
                        step_number=0,
                        timestamp="",
                        agent_name=agent_name,
                        user_id=request.user_id,
                        session_id=session_id,
                        tenant_id=request.tenant_id,
                        test_case_id=request.test_case_id,
                        event_type="sandbox_initializing",
                        status="initializing",
                    )
                )
                return await original_init(agent_name)

            async def ready_and_stream(agent_name: str, sandbox_id: str):
                await step_queue.put(
                    StepExecutionSchema(
                        step_number=0,
                        timestamp="",
                        agent_name=agent_name,
                        user_id=request.user_id,
                        session_id=session_id,
                        tenant_id=request.tenant_id,
                        test_case_id=request.test_case_id,
                        event_type="sandbox_ready",
                        status="ready",
                        sandbox_id=sandbox_id,
                    )
                )
                return await original_ready(agent_name, sandbox_id)

            # Apply patches
            webhook_module.webhook_client.send_step_data = send_and_stream
            webhook_module.webhook_client.send_sandbox_initializing = init_and_stream
            webhook_module.webhook_client.send_sandbox_ready = ready_and_stream

            # Generate session_id first
            import uuid
            from datetime import datetime

            # Add microseconds and random UUID to prevent collisions
            session_id = (
                datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + f"_{uuid.uuid4().hex[:8]}"
            )

            # Create session in Firestore IMMEDIATELY (before any steps)
            await firestore_client.create_session(
                session_id=session_id,
                sandbox_id=None,
                agent_name="E2BTestOpsAI",
                prompt=request.prompt,
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                test_case_id=request.test_case_id,
            )

            # Send session created to client
            yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id, 'user_id': request.user_id, 'tenant_id': request.tenant_id, 'test_case_id': request.test_case_id, 'prompt': request.prompt})}\n\n"

            # Now initialize sandbox
            yield f"data: {json.dumps({'type': 'initializing', 'message': 'Creating E2B sandbox...'})}\n\n"

            # Create agent with session_id, user_id, tenant_id, and test_case_id
            agent = await E2BTestOpsAI.create(
                session_id=session_id,
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                test_case_id=request.test_case_id,
            )

            # Set max_steps from request (default to 20 if not provided)
            agent.max_steps = request.max_steps if request.max_steps else 20
            print(f"✅ Agent max_steps set to: {agent.max_steps}")

            sandbox_id = agent.sandbox.id

            # Update session with sandbox_id
            await firestore_client.update_session_sandbox_id(session_id, sandbox_id)

            # Create events for external control
            stop_event = asyncio.Event()
            pause_event = asyncio.Event()

            # Store session in memory with steps collector
            active_sessions[session_id] = {
                "agent": agent,
                "status": "running",
                "sandbox_id": sandbox_id,
                "stop_event": stop_event,
                "pause_event": pause_event,
                "all_steps": [],  # Collect all steps here
            }

            yield f"data: {json.dumps({'type': 'sandbox_ready', 'session_id': session_id, 'sandbox_id': sandbox_id})}\n\n"

            # Get VNC WebSocket URL for noVNC library
            vnc_url = None
            if hasattr(agent.sandbox, "sandbox"):
                try:
                    host = agent.sandbox.sandbox.get_host(6080)
                    vnc_url = (
                        f"wss://{host}/websockify"  # Secure WebSocket URL for noVNC
                    )

                    yield f"data: {json.dumps({'type': 'vnc_url', 'url': vnc_url})}\n\n"

                    # Update session with VNC WebSocket URL
                    await firestore_client.update_session_vnc_url(session_id, vnc_url)
                except:
                    pass

            # Hook into agent's think method to capture tool calls
            original_think = agent.think

            async def think_with_events():
                result = await original_think()

                # After thinking, send the tool calls
                if agent.tool_calls:
                    import json as json_lib

                    tools_data = []

                    for tc in agent.tool_calls:
                        tool_data = {
                            "tool_name": tc.function.name,
                            "arguments": json_lib.loads(tc.function.arguments),
                        }
                        tools_data.append(tool_data)

                    await step_queue.put(
                        {
                            "type": "step_start",
                            "step_number": agent.current_step,
                            "tools": tools_data,
                        }
                    )

                return result

            agent.think = think_with_events

            # Start execution
            yield f"data: {json.dumps({'type': 'executing', 'prompt': request.prompt})}\n\n"

            # Run agent in background and stream events concurrently
            async def run_agent_task():
                try:
                    # Use custom run loop that checks pause_event
                    agent.messages.append(Message.user_message(request.prompt))
                    
                    while agent.state != AgentState.FINISHED and agent.current_step < agent.max_steps:
                        # Check for pause before each step
                        while pause_event.is_set():
                            await asyncio.sleep(1)
                            if stop_event.is_set():
                                break
                        
                        # Check for stop
                        if stop_event.is_set():
                            break
                        
                        # Execute one step
                        await agent.step()
                    
                except Exception as e:
                    print(f"Agent error: {e}")
                finally:
                    await step_queue.put(None)  # Signal completion

            agent_task = asyncio.create_task(run_agent_task())

            # Stream step events as they arrive (concurrent with agent execution)
            while True:
                # Check for external termination
                if stop_event.is_set():
                    yield f"data: {json.dumps({'type': 'terminated', 'message': 'Session terminated externally'})}\n\n"
                    break
                
                # Check if we should pause
                if pause_event.is_set():
                    active_sessions[session_id]["status"] = "paused"
                    yield f"data: {json.dumps({'type': 'paused', 'message': 'Execution paused'})}\n\n"
                    
                    # Wait while paused
                    while pause_event.is_set():
                        await asyncio.sleep(1)
                        if stop_event.is_set():  # Can terminate while paused
                            break
                    
                    # Resumed
                    if not stop_event.is_set():
                        active_sessions[session_id]["status"] = "running"
                        yield f"data: {json.dumps({'type': 'resumed', 'message': 'Execution resumed'})}\n\n"

                try:
                    # Get step with timeout to check stop_event periodically
                    step_data = await asyncio.wait_for(step_queue.get(), timeout=1.0)

                    if step_data is None:
                        # Agent completed
                        break

                    # Check if it's a step_start event or full step data
                    if isinstance(step_data, dict):
                        # Direct event (step_start, human_input_required, etc.)
                        yield f"data: {json.dumps(step_data)}\n\n"
                        # SSE event sent (suppress debug log)

                        # If it's human_input_required, also log it
                        if step_data.get("type") == "human_input_required":
                            print(
                                f"❓ Agent waiting for human response to: {step_data.get('question', '')[:80]}..."
                            )
                    else:
                        # StepExecutionSchema (step complete)
                        event_data = step_data.model_dump()
                        yield f"data: {json.dumps({'type': 'step_complete', 'data': event_data})}\n\n"
                        # SSE event sent (suppress debug log)

                except asyncio.TimeoutError:
                    # No data yet, check stop_event again
                    continue

            # Cancel agent task if still running
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass

            # Send completion
            yield f"data: {json.dumps({'type': 'completed', 'status': 'success'})}\n\n"

            # Update session status in Firestore
            await firestore_client.update_session_status(session_id, "completed")

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            # Update session status in Firestore
            await firestore_client.update_session_status(session_id, "error", str(e))

        finally:
            # Cleanup
            if agent:
                try:
                    # Print all collected steps from this session
                    all_steps = active_sessions.get(session_id, {}).get("all_steps", [])
                    if all_steps:
                        firestore_client.print_session_summary(session_id, all_steps)

                    # Clear VNC URL in session (sandbox terminating)
                    await firestore_client.update_session_vnc_url(session_id, None)

                    await agent.cleanup()
                    yield f"data: {json.dumps({'type': 'cleanup', 'message': 'Sandbox terminated'})}\n\n"
                except:
                    pass

                # Remove from active sessions
                if session_id in active_sessions:
                    del active_sessions[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/agent/terminate/{session_id}")
async def terminate_session(session_id: str):
    """Terminate a running agent session"""
    if session_id not in active_sessions:
        # Provide helpful error message
        active_count = len(active_sessions)
        active_ids = list(active_sessions.keys())
        raise HTTPException(
            status_code=404, 
            detail=f"Session '{session_id}' not found in active sessions. Active sessions: {active_count}. Use GET /agent/sessions to list active sessions."
        )

    try:
        session = active_sessions[session_id]
        agent = session["agent"]
        stop_event = session["stop_event"]

        # Signal SSE to stop
        stop_event.set()

        # Print all collected steps from this session
        all_steps = active_sessions[session_id].get("all_steps", [])
        if all_steps:
            firestore_client.print_session_summary(session_id, all_steps)

        # Clear VNC URL and update status
        await firestore_client.update_session_vnc_url(session_id, None)
        await firestore_client.update_session_status(
            session_id, "terminated", "Manually terminated"
        )

        # Cleanup agent
        await agent.cleanup()

        # Remove from active sessions
        del active_sessions[session_id]

        return {
            "status": "terminated",
            "session_id": session_id,
            "message": "Agent session terminated successfully",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/pause/{session_id}")
async def pause_session(session_id: str):
    """Pause a running agent session (execution stops but state is preserved)"""
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Use GET /agent/sessions to list active sessions."
        )
    
    try:
        session = active_sessions[session_id]
        pause_event = session["pause_event"]
        
        # Set pause flag
        pause_event.set()
        
        # Update Firestore
        await firestore_client.update_session_status(session_id, "paused", "Paused by user")
        
        return {
            "status": "paused",
            "session_id": session_id,
            "message": "Agent execution paused. Use /agent/resume to continue."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class InterventionRequest(BaseModel):
    message: str  # Guidance message to inject


@app.post("/agent/intervene/{session_id}")
async def intervene_session(session_id: str, request: InterventionRequest):
    """Inject a guidance message and guide the agent
    
    This automatically:
    1. Pauses the agent (if not already paused)
    2. Injects your guidance message into the conversation
    3. Resumes the agent with the new guidance
    
    The message will be added to the agent's conversation as a user message
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Use GET /agent/sessions to list active sessions."
        )
    
    try:
        session = active_sessions[session_id]
        agent = session["agent"]
        pause_event = session["pause_event"]
        
        was_already_paused = pause_event.is_set()
        
        # Step 1: Pause if not already paused
        if not was_already_paused:
            pause_event.set()
            await firestore_client.update_session_status(session_id, "paused", "Auto-paused for intervention")
            # Give it a moment to actually pause
            await asyncio.sleep(0.5)
        
        # Step 2: Inject user message with URGENT prefix to get model's attention
        intervention_text = (
            f"🚨 URGENT USER INTERVENTION - PRIORITY INSTRUCTION:\n\n"
            f"{request.message}\n\n"
            f"This is a direct instruction from the user. Follow this guidance IMMEDIATELY, "
            f"even if it means deviating from the plan, stopping execution, or using the terminate() tool."
        )
        user_msg = Message.user_message(intervention_text)
        agent.messages.append(user_msg)
        
        # Save intervention to Firestore for tracking
        await firestore_client.save_step(
            StepExecutionSchema(
                step_number=agent.current_step,
                timestamp=datetime.utcnow().isoformat() + "Z",
                agent_name=agent.name,
                user_id=getattr(agent, "user_id", None),
                session_id=session_id,
                thinking=f"[HUMAN INTERVENTION] {request.message}",
                tool_calls=[],
                tool_results=[],
                screenshots=[],
                screenshot_urls=[],
                status="intervention",
            ),
            []
        )
        
        # Step 3: Auto-resume
        pause_event.clear()
        await firestore_client.update_session_status(session_id, "running", "Auto-resumed after intervention")
        
        return {
            "status": "intervention_complete",
            "session_id": session_id,
            "was_paused": was_already_paused,
            "message": f"Guidance injected and agent resumed: '{request.message}'"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/resume/{session_id}")
async def resume_session(session_id: str):
    """Resume a paused agent session"""
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Use GET /agent/sessions to list active sessions."
        )
    
    try:
        session = active_sessions[session_id]
        pause_event = session["pause_event"]
        
        # Clear pause flag
        pause_event.clear()
        
        # Update Firestore
        await firestore_client.update_session_status(session_id, "running", "Resumed by user")
        
        return {
            "status": "resumed",
            "session_id": session_id,
            "message": "Agent execution resumed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/sessions")
async def list_sessions():
    """List all active sessions"""
    sessions = []
    for session_id, session_data in active_sessions.items():
        sessions.append(
            {
                "session_id": session_id,
                "status": session_data["status"],
                "sandbox_id": session_data["sandbox_id"],
            }
        )
    return {"active_sessions": len(sessions), "sessions": sessions}


@app.post("/agent/respond/{session_id}")
async def respond_to_agent(session_id: str, request: Request):
    """Send human response to agent that's waiting for input"""
    try:
        body = await request.json()
        answer = body.get("answer", "")

        if session_id not in human_response_queues:
            raise HTTPException(
                status_code=404, detail="No pending question for this session"
            )

        # Put answer in queue - agent is waiting on this
        queue_data = human_response_queues[session_id]
        await queue_data["queue"].put(answer)

        # Update Firestore with human response
        await firestore_client.update_human_response(
            session_id, queue_data["step_number"], answer
        )

        return {
            "status": "success",
            "session_id": session_id,
            "message": "Response delivered to agent",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "E2B Agent API",
        "active_sessions": len(active_sessions),
    }


@app.post("/agent/replay/{tenant_id}/{test_case_id}")
async def replay_proven_steps(tenant_id: str, test_case_id: str):
    """
    Replay proven successful steps from a test case
    
    Creates a new sandbox and executes the exact tool calls that worked,
    including assertions to validate the test still passes.
    
    Zero AI cost - deterministic replay with validation.
    """
    async def replay_generator():
        agent = None
        execution_id = None
        
        try:
            from app.agent.e2b_agent import E2BTestOpsAI
            from datetime import datetime
            
            # Generate execution ID immediately
            execution_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_replay"
            
            # Get test case to fetch proven steps
            doc_ref = firestore_client.db.collection("test_cases").document(test_case_id)
            test_case_data = doc_ref.get().to_dict() if doc_ref.get().exists else None
            
            if not test_case_data:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Test case not found'})}\n\n"
                return
            
            proven_steps = test_case_data.get("proven_steps", [])
            session_id = test_case_data.get("session_id", "unknown")
            user_id = f"{tenant_id}_replay_user"
            
            if not proven_steps:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No proven steps found for this test case. Run ai_proven_steps first.'})}\n\n"
                return
            
            # Create execution record IMMEDIATELY (before sandbox creation)
            await firestore_client.create_execution(
                execution_id=execution_id,
                user_id=user_id,
                session_id=session_id,
                sandbox_id=None,  # Will be updated after sandbox creation
                vnc_url=None
            )
            
            yield f"data: {json.dumps({'type': 'replay_start', 'session_id': session_id, 'execution_id': execution_id})}\n\n"
            yield f"data: {json.dumps({'type': 'steps_loaded', 'count': len(proven_steps)})}\n\n"
            
            # Create E2B sandbox
            yield f"data: {json.dumps({'type': 'initializing', 'message': 'Creating sandbox...'})}\n\n"
            
            # Create agent WITHOUT saving steps to Firestore
            # Temporarily disable Firestore to avoid saving replay steps
            firestore_was_enabled = firestore_client.enabled
            firestore_client.enabled = False
            
            agent = await E2BTestOpsAI.create(
                session_id=execution_id,
                user_id="replay_user"
            )
            
            # Re-enable Firestore
            firestore_client.enabled = firestore_was_enabled
            
            # Get VNC URL and update execution record with sandbox info
            vnc_url = None
            if hasattr(agent.sandbox, "sandbox"):
                try:
                    host = agent.sandbox.sandbox.get_host(6080)
                    vnc_url = f"wss://{host}/websockify"
                except:
                    pass
            
            # Update execution record with sandbox_id and VNC URL
            await firestore_client.update_execution_status(
                execution_id=execution_id,
                status="running",
                vnc_url=vnc_url
            )
            
            # Also update sandbox_id separately
            doc_ref = firestore_client.db.collection("agent_sessions_executions").document(execution_id)
            doc_ref.update({
                "sandbox_id": agent.sandbox.id,
                "vnc_url": vnc_url,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            })
            
            yield f"data: {json.dumps({'type': 'sandbox_ready', 'execution_id': execution_id, 'sandbox_id': agent.sandbox.id, 'vnc_url': vnc_url})}\n\n"
            
            # Helper function to add smart waits before action
            async def add_smart_wait_before(tool, action, arguments, next_action):
                """Add smart waits before executing an action based on context"""
                
                # After navigate_to, always wait for network idle
                if action == "navigate_to":
                    # Will be added after the navigate executes
                    pass
                
                # Before click_element, Playwright auto-waits (no extra wait needed)
                # After click_element, wait based on what's next
                elif action == "click_element" and next_action:
                    pass  # Will be added after click executes
                
                # No special wait needed for other actions (Playwright handles it)
            
            async def add_smart_wait_after(tool, action, arguments, next_action):
                """Add smart waits after executing an action based on what's next"""
                
                if action == "navigate_to":
                    # After navigation, wait for DOM to be ready
                    try:
                        await tool.execute(action="wait_for_load_state", load_state="domcontentloaded")
                        yield f"data: {json.dumps({'type': 'smart_wait', 'reason': 'DOM ready'})}\n\n"
                    except:
                        pass  # Continue even if wait fails
                
                elif action == "click_element" and next_action:
                    next_act = next_action.get("arguments", {}).get("action", "")
                    
                    # If next action is input, wait for DOM to be ready
                    if next_act == "input_text":
                        try:
                            await tool.execute(action="wait_for_load_state", load_state="domcontentloaded")
                            yield f"data: {json.dumps({'type': 'smart_wait', 'reason': 'DOM ready for input'})}\n\n"
                        except:
                            pass
                    # If next action is another click, brief pause for animations/updates
                    elif next_act == "click_element":
                        await asyncio.sleep(0.5)
                        yield f"data: {json.dumps({'type': 'smart_wait', 'reason': 'DOM update pause'})}\n\n"
            
            # Execute each proven step (new format from ai_proven_steps)
            for idx, proven_step in enumerate(proven_steps):
                step_number = proven_step.get("step_number", idx + 1)
                tool_name = proven_step.get("tool_name")
                arguments = proven_step.get("arguments", {})
                
                yield f"data: {json.dumps({'type': 'step_start', 'step_number': step_number, 'tool_name': tool_name})}\n\n"
                
                # Print to console
                print(f"Replaying Step {step_number}: {tool_name} {arguments.get('action', '')}")
                
                # Execute the tool call
                try:
                    tool = agent.available_tools.get_tool(tool_name)
                    if not tool:
                        print(f"❌ Tool {tool_name} not found")
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Tool {tool_name} not found'})}\n\n"
                        continue
                    
                    # Get next action for smart wait inference
                    next_action = proven_steps[idx + 1] if idx + 1 < len(proven_steps) else None
                    
                    # Execute the action with fallback for element-based actions
                    action = arguments.get("action", "") if tool_name == "e2b_browser" else ""
                    
                    # Try original index first
                    result = await tool.execute(**arguments)
                    has_error = hasattr(result, 'error') and result.error
                    
                    # If click/input failed and we have element metadata, try to find by metadata
                    if tool_name == "e2b_browser" and action in ["click_element", "input_text"]:
                        if has_error and "_element_metadata" in arguments:
                            metadata = arguments["_element_metadata"]
                            print(f"🔄 Element index {arguments.get('index')} failed, trying to find by metadata: text='{metadata.get('text', '')}' id='{metadata.get('id', '')}' class='{metadata.get('class', '')}'")
                            
                            # Get current elements
                            elements_result = await tool.execute(action="get_elements")
                            elements_str = str(elements_result)
                            
                            # Try to find matching element by text, id, or class
                            new_index = None
                            best_match_score = 0
                            lines = elements_str.split('\n')
                            
                            for line in lines:
                                if not line.strip().startswith('['):
                                    continue
                                
                                # Check if this element matches our metadata
                                matches = 0
                                if metadata.get("text") and metadata["text"] and metadata["text"] in line:
                                    matches += 3  # Text match is most important
                                if metadata.get("id") and metadata["id"] and f"id='{metadata['id']}'" in line:
                                    matches += 2  # ID match is very specific
                                if metadata.get("class") and metadata["class"] and metadata["class"] in line:
                                    matches += 1  # Class match is helpful
                                
                                if matches > best_match_score:
                                    # Extract index from line like "[5] button..."
                                    try:
                                        new_index = int(line.split(']')[0].strip('['))
                                        best_match_score = matches
                                        if matches >= 4:  # Perfect match, stop searching
                                            break
                                    except:
                                        pass
                            
                            # Retry with new index if found with good confidence
                            if new_index is not None and best_match_score >= 2:
                                retry_args = arguments.copy()
                                retry_args["index"] = new_index
                                del retry_args["_element_metadata"]  # Remove metadata from retry
                                result = await tool.execute(**retry_args)
                                has_error = hasattr(result, 'error') and result.error
                                print(f"🔄 Retried {action} with new index {new_index} (match score: {best_match_score}): {'SUCCESS' if not has_error else 'FAILED'}")
                            else:
                                print(f"❌ Could not find element by metadata (best match score: {best_match_score})")
                            
                    # Convert ToolResult to string
                    result_str = str(result)
                    
                    # Add smart waits after action (inferred from next action)
                    if not has_error and tool_name == "e2b_browser":
                        try:
                            async for wait_event in add_smart_wait_after(tool, action, arguments, next_action):
                                yield wait_event
                        except Exception as wait_error:
                            # Log wait error but continue
                            print(f"⚠️ Smart wait failed: {wait_error}")
                            pass
                    
                    success = not has_error
                    result_preview = result_str[:200]
                    
                    # Print result
                    status = "✅" if success else "❌"
                    print(f"  {status} {result_preview[:100]}")
                    
                    # Save execution step to Firestore
                    await firestore_client.save_execution_step(
                        execution_id=execution_id,
                        session_id=test_case_id,  # Use test_case_id as session ref
                        user_id=user_id,
                        step_index=step_number,
                        tool_name=tool_name,
                        arguments=arguments,
                        success=success,
                        result=result_str  # Full result, not just preview
                    )
                    
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': tool_name, 'success': success, 'result': result_preview})}\n\n"
                except Exception as tool_error:
                    # Log individual tool execution errors
                    import traceback
                    error_msg = str(tool_error)
                    error_trace = traceback.format_exc()
                    print(f"\n❌ TOOL EXECUTION ERROR:")
                    print(f"   Tool: {tool_name}")
                    print(f"   Args: {arguments}")
                    print(f"   Error: {error_msg}")
                    print(f"   Trace: {error_trace}\n")
                    
                    # Save error to Firestore
                    await firestore_client.save_execution_step(
                        execution_id=execution_id,
                        session_id=test_case_id,
                        user_id=user_id,
                        step_index=step_number,
                        tool_name=tool_name,
                        arguments=arguments,
                        success=False,
                        result=f"Error: {error_msg}"
                    )
                    
                    yield f"data: {json.dumps({'type': 'tool_error', 'tool_name': tool_name, 'error': error_msg})}\n\n"
            
            yield f"data: {json.dumps({'type': 'replay_complete', 'steps_executed': len(proven_steps), 'execution_id': execution_id})}\n\n"
            
        except Exception as e:
            # Log the error with full traceback
            import traceback
            error_msg = str(e)
            error_trace = traceback.format_exc()
            print(f"\n{'='*70}")
            print(f"❌ REPLAY ERROR")
            print(f"{'='*70}")
            print(f"Error: {error_msg}")
            print(f"Traceback:\n{error_trace}")
            print(f"{'='*70}\n")
            
            # Mark execution as failed
            if execution_id:
                try:
                    await firestore_client.update_execution_status(execution_id, "failed", vnc_url=None)
                except:
                    pass
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'traceback': error_trace})}\n\n"
        finally:
            # Cleanup sandbox and update execution record
            if agent:
                await agent.cleanup()
            
            # Clear VNC URL in execution record (sandbox deleted)
            if execution_id:
                try:
                    await firestore_client.update_execution_status(execution_id, "completed", vnc_url=None)
                    print(f"✅ Execution {execution_id} VNC URL cleared (sandbox deleted)")
                except:
                    pass
            
            yield f"data: {json.dumps({'type': 'cleanup_complete', 'sandbox_deleted': True, 'execution_id': execution_id})}\n\n"

    return StreamingResponse(replay_generator(), media_type="text/event-stream")


@app.post("/api/runs/execute")
async def execute_run(request: RunExecuteRequest):
    """
    Execute a run by replaying all test cases sequentially (async)
    
    Returns immediately while execution happens in background.
    Frontend watches Firestore for real-time progress updates.
    """
    run_id = request.run_id
    tenant_id = request.tenant_id
    
    # Validate run exists
    run_ref = firestore_client.db.collection("runs").document(run_id)
    run_doc = run_ref.get()
    
    if not run_doc.exists:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = run_doc.to_dict()
    test_case_ids = run_data.get("test_case_ids", [])
    
    if not test_case_ids:
        raise HTTPException(status_code=400, detail="No test cases in run")
    
    # Clear previous execution data if re-running
    # Initialize fresh results for all test cases
    fresh_results = {}
    for tc_id in test_case_ids:
        fresh_results[tc_id] = {
            "test_case_id": tc_id,
            "status": "pending",
            "current_step": 0,
            "total_steps": 0,
            "passed_steps": 0,
            "failed_steps": 0,
            "vnc_url": None,
            "started_at": None,
            "completed_at": None,
            "error": None
        }
    
    # Update run status to running with fresh results
    run_ref.update({
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "current_test_case_index": 0,
        "results": fresh_results,  # Reset all previous results
        "error": None
    })
    
    # Start execution in background
    async def execute_run_background():
        """Background task to execute all test cases"""
        try:
            mode = "PARALLEL" if request.parallel else "SEQUENTIAL"
            print(f"\n{'='*70}")
            print(f"🏃 EXECUTING RUN: {run_id} ({mode})")
            print(f"{'='*70}")
            print(f"Tenant: {tenant_id}")
            print(f"Test Cases: {len(test_case_ids)}")
            print(f"{'='*70}\n")
            
            if request.parallel:
                # Execute test cases in parallel
                print(f"🚀 Starting {len(test_case_ids)} test cases in PARALLEL...\n")
                
                async def execute_single_test_case(index, test_case_id):
                    """Execute a single test case"""
                    print(f"[Test {index + 1}] Starting: {test_case_id}")
                    
                    # Create callback for real-time updates
                    async def update_run(updates: dict):
                        run_ref.update(updates)
                    
                    # Execute test case
                    result = await execute_test_case_proven_steps(
                        tenant_id=tenant_id,
                        test_case_id=test_case_id,
                        run_id=run_id,
                        run_updates_callback=update_run
                    )
                    
                    status_icon = "✅" if result.get("success") else "❌"
                    print(f"{status_icon} [Test {index + 1}] Complete: {result.get('status')}")
                    return result
                
                # Run all test cases in parallel with asyncio.gather
                print(f"⚡ Launching all {len(test_case_ids)} sandboxes simultaneously...")
                tasks = [
                    execute_single_test_case(i, tc_id) 
                    for i, tc_id in enumerate(test_case_ids)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                print(f"\n✅ All {len(test_case_ids)} test cases completed in parallel")
            else:
                # Execute test cases sequentially
                for index, test_case_id in enumerate(test_case_ids):
                    print(f"\n▶️  Test Case {index + 1}/{len(test_case_ids)}: {test_case_id}")
                    
                    # Update current index
                    run_ref.update({"current_test_case_index": index})
                    
                    # Create callback for real-time updates
                    async def update_run(updates: dict):
                        run_ref.update(updates)
                    
                    # Execute test case
                    result = await execute_test_case_proven_steps(
                        tenant_id=tenant_id,
                        test_case_id=test_case_id,
                        run_id=run_id,
                        run_updates_callback=update_run
                    )
                    
                    status_icon = "✅" if result.get("success") else "❌"
                    print(f"{status_icon} Test Case {index + 1}: {result.get('status')}")
            
            # Get final results
            updated_run = run_ref.get().to_dict()
            results = updated_run.get("results", {})
            
            # Aggregate status
            any_failed = any(r.get("status") == "failed" for r in results.values())
            final_status = "failed" if any_failed else "completed"
            
            # Update final run status
            run_ref.update({
                "status": final_status,
                "completed_at": datetime.now(timezone.utc).isoformat()
            })
            
            print(f"\n{'='*70}")
            print(f"🏁 RUN COMPLETE: {final_status.upper()}")
            print(f"{'='*70}\n")
            
        except Exception as e:
            print(f"\n❌ RUN ERROR: {str(e)}")
            # Mark run as failed
            try:
                run_ref.update({
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                })
            except:
                pass
    
    # Start background task
    asyncio.create_task(execute_run_background())
    
    # Return immediately
    return {
        "success": True,
        "run_id": run_id,
        "message": f"Run execution started with {len(test_case_ids)} test cases",
        "test_case_count": len(test_case_ids)
    }


if __name__ == "__main__":
    import os
    
    # Get port from environment (Cloud Run uses PORT env var)
    port = int(os.getenv("PORT", 8000))
    
    print("\n" + "=" * 70)
    print("🚀 TESTOPSAI API SERVER")
    print("=" * 70)
    print(f"\n📡 API: http://localhost:{port}")
    print(f"📖 Docs: http://localhost:{port}/docs")
    print("\n📝 Usage:")
    print("  POST /agent/start")
    print('  Body: {"prompt": "Your task here", "user_id": "user123"}')
    print("  Returns: SSE stream with execution updates")
    print("\n📝 Replay:")
    print("  POST /agent/replay/{session_id}")
    print("\n💡 Step details available via:")
    print("  - Firestore: agent_sessions, agent_sessions_executions")
    print("  - Firebase Storage: screenshots")
    print("\n" + "=" * 70 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
