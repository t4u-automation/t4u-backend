"""Firebase Firestore and Storage integration for storing step execution data"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import PROJECT_ROOT, WORKSPACE_ROOT, config
from app.webhook import StepExecutionSchema


class FirestoreClient:
    """Client for Firebase Firestore and Storage"""

    def __init__(self):
        self.enabled = False
        self.db = None
        self.storage_bucket = None
        self.collection_name = "agent_steps"
        self.storage_enabled = False

        try:
            # Check if Firestore is configured and enabled
            if hasattr(config, "firestore") and config.firestore:
                enabled = getattr(config.firestore, "enabled", False)

                if not enabled:
                    return

                service_account_path = getattr(
                    config.firestore, "service_account_path", None
                )
                collection = getattr(config.firestore, "collection", "agent_steps")
                storage_bucket = getattr(config.firestore, "storage_bucket", None)

                if service_account_path:
                    import firebase_admin
                    from firebase_admin import credentials, firestore, storage

                    # Initialize Firebase
                    cred = credentials.Certificate(service_account_path)

                    # Check if already initialized
                    if not firebase_admin._apps:
                        if storage_bucket:
                            firebase_admin.initialize_app(
                                cred, {"storageBucket": storage_bucket}
                            )
                        else:
                            firebase_admin.initialize_app(cred)

                    self.db = firestore.client()
                    self.collection_name = collection
                    self.enabled = True

                    # Initialize Storage if bucket is configured
                    if storage_bucket:
                        self.storage_bucket = storage.bucket()
                        self.storage_enabled = True
                        print(
                            f"✅ Firestore + Storage connected: {collection}, {storage_bucket}"
                        )
                    else:
                        print(f"✅ Firestore connected: {collection}")
        except Exception as e:
            print(f"⚠️  Firestore init error: {e}")
            self.enabled = False

    async def upload_screenshots(
        self, screenshot_names: List[str], user_id: str = None, session_id: str = None
    ) -> List[str]:
        """Upload screenshots to Firebase Storage and return public URLs

        Path: screenshots/{user_id}/{session_id}/{filename}
        """
        if not self.storage_enabled or not screenshot_names:
            return []

        # Use timestamp as session ID if not provided
        if not session_id:
            session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        urls = []
        try:
            for screenshot_name in screenshot_names:
                screenshot_path = WORKSPACE_ROOT / screenshot_name

                if not screenshot_path.exists():
                    continue

                # Create unique path with user_id, session ID and timestamp
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[
                    :-3
                ]  # milliseconds
                name_without_ext = screenshot_path.stem
                ext = screenshot_path.suffix
                file_name = f"{timestamp}_{name_without_ext}{ext}"

                # Upload to Storage with user_id in path
                if user_id:
                    blob_path = f"screenshots/{user_id}/{session_id}/{file_name}"
                else:
                    # Fallback to old path if user_id not provided
                    blob_path = f"screenshots/{session_id}/{file_name}"

                blob = self.storage_bucket.blob(blob_path)

                # Upload file
                blob.upload_from_filename(str(screenshot_path))

                # Make public and get URL
                blob.make_public()
                urls.append(blob.public_url)

            return urls

        except Exception as e:
            print(f"⚠️  Storage upload error: {e}")
            return []

    def _get_doc_id(self, step_data: StepExecutionSchema) -> str:
        """Generate consistent document ID for a step"""
        return f"{step_data.timestamp.replace(':', '-').replace('.', '-')}_{step_data.step_number}"

    async def save_step(
        self, step_data: StepExecutionSchema, screenshot_urls: List[str] = None
    ) -> str:
        """Save step execution data to Firestore with screenshot URLs

        Returns: document ID if successful, None otherwise
        """
        if not self.enabled:
            return None

        try:
            # Convert to dict
            data = step_data.model_dump()

            # Add screenshot URLs if provided
            if screenshot_urls:
                data["screenshot_urls"] = screenshot_urls

            # Create document ID from timestamp and step
            doc_id = self._get_doc_id(step_data)

            # Save to Firestore
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            doc_ref.set(data)

            # Suppress verbose Firestore logs (data is in agent_steps collection)
            # Only log to file, not console

            # Collect step in active_sessions if available
            try:
                from api_server import active_sessions

                session_id = step_data.session_id
                if session_id and session_id in active_sessions:
                    active_sessions[session_id]["all_steps"].append(data)
            except:
                pass  # Not in API context or session not found

            return doc_id

        except Exception as e:
            print(f"⚠️  Firestore save error: {e}")
            return None

    async def update_screenshot_urls(
        self, step_data: StepExecutionSchema, screenshot_urls: List[str]
    ) -> bool:
        """Update an existing Firestore document with screenshot URLs"""
        if not self.enabled:
            return False

        try:
            doc_id = self._get_doc_id(step_data)

            # Update document with screenshot URLs and change status
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            doc_ref.update(
                {
                    "screenshot_urls": screenshot_urls,
                    "status": "success",
                    "upload_completed_at": datetime.utcnow().isoformat() + "Z",
                }
            )

            return True

        except Exception as e:
            print(f"⚠️  Firestore update error: {e}")
            return False

    # Session management methods
    async def create_session(
        self,
        session_id: str,
        sandbox_id: str = None,
        agent_name: str = None,
        prompt: str = None,
        user_id: str = None,
        tenant_id: str = None,
        test_case_id: str = None,
    ) -> bool:
        """Create a new session in Firestore"""
        if not self.enabled:
            return False

        try:
            session_data = {
                "session_id": session_id,
                "sandbox_id": sandbox_id,  # May be None initially
                "agent_name": agent_name,
                "prompt": prompt,
                "user_id": user_id,
                "tenant_id": tenant_id,  # Tenant/Organization ID
                "test_case_id": test_case_id,  # Test Case ID
                "status": "initializing",
                "vnc_url": None,
                "artifacts": [],  # Track all files created during session
                "proven_steps": [],  # Track successful steps for replay
                "total_tokens": 0,  # Total tokens used (input + output)
                "total_cost": 0.0,  # Total cost in USD
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc_ref.set(session_data)

            return True

        except Exception as e:
            print(f"⚠️  Session create error: {e}")
            return False

    async def update_session_sandbox_id(self, session_id: str, sandbox_id: str) -> bool:
        """Update session with sandbox_id and set status to running"""
        if not self.enabled:
            return False

        try:
            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc_ref.update(
                {
                    "sandbox_id": sandbox_id,
                    "status": "running",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
            )

            return True

        except Exception as e:
            # Suppress 404 errors (session might not exist yet) - not critical
            if "404" not in str(e):
                print(f"⚠️  Session update error: {e}")
            return False

    async def update_session_status(
        self, session_id: str, status: str, message: str = None
    ) -> bool:
        """Update session status"""
        if not self.enabled:
            return False

        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

            if message:
                update_data["message"] = message

            # Set completed_at timestamp for final states
            if status in ["completed", "cancelled", "terminated", "failed"]:
                update_data["completed_at"] = datetime.utcnow().isoformat() + "Z"

            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc_ref.update(update_data)

            return True

        except Exception as e:
            # Suppress 404 errors (session might not exist yet) - not critical
            if "404" not in str(e):
                print(f"⚠️  Session update error: {e}")
            return False

    async def update_session_last_output(
        self, session_id: str, step_number: int, output: str
    ) -> bool:
        """Update session with last step output"""
        if not self.enabled:
            return False

        try:
            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc_ref.update(
                {
                    "last_output": output,
                    "last_step": step_number,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
            )

            return True

        except Exception as e:
            # Suppress 404 errors (session might not exist yet) - not critical
            if "404" not in str(e):
                print(f"⚠️  Session update error: {e}")
            return False

    async def update_session_vnc_url(
        self, session_id: str, vnc_url: str = None
    ) -> bool:
        """Update session VNC URL (set to None when sandbox terminated)"""
        if not self.enabled:
            return False

        try:
            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc_ref.update(
                {"vnc_url": vnc_url, "updated_at": datetime.utcnow().isoformat() + "Z"}
            )

            return True

        except Exception as e:
            print(f"⚠️  VNC URL update error: {e}")
            return False

    async def update_human_response(
        self, session_id: str, step_number: int, response: str
    ) -> bool:
        """Update step in agent_steps collection with human response"""
        if not self.enabled:
            return False

        try:
            # Find the step document with human_input_required event
            doc_id = f"{session_id}_step_{step_number}"
            doc_ref = self.db.collection(self.collection_name).document(doc_id)

            # Update with human response
            doc_ref.update(
                {
                    "human_response": response,
                    "status": "completed",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
            )

            return True
        except Exception as e:
            print(f"⚠️  Error updating human response: {e}")
            return False

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename extension"""
        import mimetypes

        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"

    async def upload_artifact(
        self,
        user_id: str,
        session_id: str,
        file_path: str,
        file_content: bytes,
        step_number: int,
    ) -> Optional[str]:
        """
        Upload file artifact to Firebase Storage with user_id folder

        Path: artifacts/{user_id}/{session_id}/{filename}

        Args:
            user_id: Firebase UID of the user
            session_id: Session ID
            file_path: Original file path in E2B (e.g., /home/user/test.html)
            file_content: File content as bytes
            step_number: Step number when file was created

        Returns:
            Public URL of uploaded file, or None if failed
        """
        if not self.storage_enabled:
            print("⚠️  Firebase Storage not enabled, skipping artifact upload")
            return None

        try:
            # 1. Extract filename from path
            file_name = file_path.split("/")[-1]

            # 2. Generate storage path with user_id
            storage_path = f"artifacts/{user_id}/{session_id}/{file_name}"

            # 3. Upload to Firebase Storage
            blob = self.storage_bucket.blob(storage_path)
            blob.upload_from_string(file_content)
            blob.make_public()

            # 4. Get public URL
            public_url = blob.public_url

            # 5. Create artifact metadata
            artifact = {
                "file_name": file_name,
                "file_path": file_path,
                "storage_path": storage_path,
                "storage_url": public_url,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "step_number": step_number,
                "file_size": len(file_content),
                "file_type": self._get_mime_type(file_name),
            }

            # 6. Update session artifacts
            await self.add_artifact_to_session(session_id, artifact)

            print(f"📤 Artifact uploaded: {file_name} → {storage_path}")

            return public_url

        except Exception as e:
            print(f"⚠️  Error uploading artifact: {e}")
            return None

    async def add_artifact_to_session(self, session_id: str, artifact: Dict) -> bool:
        """Add artifact to session's artifacts array"""
        if not self.enabled:
            return False

        try:
            from firebase_admin import firestore

            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc_ref.update(
                {
                    "artifacts": firestore.ArrayUnion([artifact]),
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
            )

            return True

        except Exception as e:
            print(f"⚠️  Error adding artifact to session: {e}")
            return False

    async def update_session_costs(
        self, session_id: str, total_tokens: int, total_cost: float
    ) -> bool:
        """Update session with cumulative token count and cost"""
        if not self.enabled:
            print("Firestore not enabled, skipping cost update")
            return False

        try:
            rounded_cost = round(total_cost, 4)
            # Cost update (suppressed from console)

            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc_ref.update(
                {
                    "total_tokens": total_tokens,
                    "total_cost": rounded_cost,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
            )
            
            # Costs updated (suppressed from console)
            return True

        except Exception as e:
            print(f"⚠️  Error updating session costs: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def add_proven_step(
        self, session_id: str, step_index: int, step_description: str, tool_calls: List[Dict]
    ) -> bool:
        """Add a proven successful step to the session for later replay
        
        Args:
            session_id: Session ID
            step_index: Index of the plan step that was completed
            step_description: Description of what this step does
            tool_calls: List of successful tool calls that completed this step
        """
        if not self.enabled:
            return False

        try:
            from firebase_admin import firestore

            proven_step = {
                "step_index": step_index,
                "description": step_description,
                "tool_calls": tool_calls,
                "added_at": datetime.utcnow().isoformat() + "Z",
            }

            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc_ref.update(
                {
                    "proven_steps": firestore.ArrayUnion([proven_step]),
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
            )

            # Proven step saved (suppressed from console)
            return True

        except Exception as e:
            print(f"⚠️  Error adding proven step: {e}")
            return False
    
    async def save_execution_history_to_test_case(
        self,
        test_case_id: str,
        session_id: str,
        execution_history: List[Dict],
        summary: str = None
    ) -> bool:
        """
        Save execution history to test_case for AI analysis
        
        Args:
            test_case_id: Test case ID
            session_id: Session ID that completed this test case
            execution_history: Complete list of all steps with thinking, actions, results
            summary: Optional summary of what was accomplished
            
        Returns:
            True if successful
        """
        if not self.enabled or not test_case_id:
            return False
        
        try:
            # Save to test_cases collection
            doc_ref = self.db.collection("test_cases").document(test_case_id)
            
            # Update or create test case with execution history
            doc_ref.set({
                "test_case_id": test_case_id,
                "session_id": session_id,
                "execution_history_raw": execution_history,  # All steps for AI analysis
                "summary": summary,
                "total_steps": len(execution_history),
                "status": "pending_analysis",  # Cloud Function will process this
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }, merge=True)
            
            print(f"✅ Saved {len(execution_history)} steps to test_case {test_case_id} for AI analysis")
            return True
            
        except Exception as e:
            print(f"⚠️  Error saving execution history to test_case: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data from Firestore"""
        if not self.enabled:
            return None

        try:
            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None

        except Exception as e:
            print(f"⚠️  Error getting session: {e}")
            return None

    async def get_proven_steps(self, session_id: str) -> List[Dict]:
        """Get proven steps from a session for replay"""
        if not self.enabled:
            return []

        try:
            doc_ref = self.db.collection("agent_sessions").document(session_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return data.get("proven_steps", [])
            return []

        except Exception as e:
            print(f"⚠️  Error getting proven steps: {e}")
            return []

    async def create_execution(
        self,
        execution_id: str,
        user_id: str,
        session_id: str,
        sandbox_id: str = None,
        vnc_url: str = None
    ) -> bool:
        """Create a new execution record in agent_sessions_executions
        
        Args:
            execution_id: Unique ID for this execution (e.g., timestamp_replay)
            user_id: User who triggered the replay
            session_id: Original session ID being replayed
            sandbox_id: E2B sandbox ID
            vnc_url: VNC URL for watching the execution
        """
        if not self.enabled:
            return False

        try:
            execution_data = {
                "execution_id": execution_id,
                "user_id": user_id,
                "session_id": session_id,  # Links to original session
                "sandbox_id": sandbox_id,
                "vnc_url": vnc_url,
                "status": "running",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

            doc_ref = self.db.collection("agent_sessions_executions").document(execution_id)
            doc_ref.set(execution_data)

            print(f"✅ Execution {execution_id} created in Firestore")
            return True

        except Exception as e:
            print(f"⚠️  Execution create error: {e}")
            return False

    async def update_execution_status(
        self, execution_id: str, status: str, vnc_url: str = None
    ) -> bool:
        """Update execution status and optionally VNC URL
        
        Args:
            execution_id: Execution ID
            status: Status (running, completed, failed)
            vnc_url: VNC URL (None to clear after cleanup)
        """
        if not self.enabled:
            return False

        try:
            update_data = {
                "status": status,
                "vnc_url": vnc_url,  # Always set vnc_url (None to clear)
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
            
            if status == "completed":
                update_data["completed_at"] = datetime.utcnow().isoformat() + "Z"

            doc_ref = self.db.collection("agent_sessions_executions").document(execution_id)
            doc_ref.update(update_data)

            print(f"✅ Execution {execution_id} updated: {status}, vnc_url={'cleared' if vnc_url is None else 'set'}")
            return True

        except Exception as e:
            print(f"⚠️  Execution update error: {e}")
            return False

    def _generate_step_description(self, tool_name: str, arguments: dict) -> str:
        """Generate human-readable description from tool call"""
        if tool_name == "e2b_browser":
            action = arguments.get("action", "")
            
            if action == "navigate_to":
                url = arguments.get("url", "")
                return f"Navigate to {url}"
            
            elif action == "click_element":
                index = arguments.get("index", "")
                return f"Click element [{index}]"
            
            elif action == "input_text":
                index = arguments.get("index", "")
                text = arguments.get("text", "")
                # Truncate long text
                text_preview = text[:50] + "..." if len(text) > 50 else text
                return f"Input text at [{index}]: '{text_preview}'"
            
            elif action == "wait":
                seconds = arguments.get("seconds", "")
                return f"Wait {seconds} seconds"
            
            elif action == "scroll_down":
                amount = arguments.get("amount", "")
                return f"Scroll down {amount}px"
            
            elif action == "scroll_up":
                amount = arguments.get("amount", "")
                return f"Scroll up {amount}px"
            
            elif action == "go_back":
                return "Go back"
            
            elif action == "send_keys":
                keys = arguments.get("keys", "")
                return f"Send keys: {keys}"
            
            elif action == "select_dropdown_option":
                index = arguments.get("index", "")
                text = arguments.get("text", "")
                return f"Select dropdown [{index}]: {text}"
            
            else:
                return f"{action}"
        
        return f"{tool_name}"

    async def save_execution_step(
        self,
        execution_id: str,
        session_id: str,
        user_id: str,
        step_index: int,
        tool_name: str,
        arguments: dict,
        success: bool,
        result: str
    ) -> bool:
        """Save a single tool execution step during replay
        
        Args:
            execution_id: Execution ID
            session_id: Original session ID
            user_id: User ID
            step_index: Which plan step this belongs to
            tool_name: Name of tool executed
            arguments: Tool arguments
            success: Whether tool execution succeeded
            result: Tool result/output
        """
        if not self.enabled:
            return False

        try:
            # Generate human-readable description
            description = self._generate_step_description(tool_name, arguments)
            
            step_data = {
                "execution_id": execution_id,
                "session_id": session_id,
                "user_id": user_id,
                "step_index": step_index,
                "tool_name": tool_name,
                "arguments": arguments,
                "description": description,  # Human-readable!
                "success": success,
                "result": result,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

            # Use a unique document ID: execution_id + step_index + timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            doc_id = f"{execution_id}_{step_index}_{timestamp}"
            
            doc_ref = self.db.collection("agent_sessions_executions_steps").document(doc_id)
            doc_ref.set(step_data)

            return True

        except Exception as e:
            print(f"⚠️  Error saving execution step: {e}")
            return False

    def print_session_summary(self, session_id: str, steps: List[Dict]):
        """Print all session steps as formatted JSON for frontend consumption"""
        print(f"\n\n{'='*70}")
        print(f"{'='*70}")
        print(f"🎯 SESSION COMPLETE SUMMARY - FOR FRONTEND")
        print(f"{'='*70}")
        print(f"Session ID: {session_id}")
        print(f"Total Steps: {len(steps)}")
        print(f"{'='*70}\n")
        print("SESSION STEPS JSON (Copy this for frontend):")
        print(f"{'='*70}")
        print(
            json.dumps(
                {"session_id": session_id, "total_steps": len(steps), "steps": steps},
                indent=2,
                default=str,
            )
        )
        print(f"{'='*70}")
        print(f"{'='*70}\n")


# Global Firestore client
firestore_client = FirestoreClient()
