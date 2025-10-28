"""Google Gemini API client implementation"""

import json
import time
from typing import Any, Dict, List, Optional

import google.generativeai as genai


class GeminiToolCall:
    """Tool call wrapper to match OpenAI format"""

    def __init__(self, call_id: str, function_name: str, arguments: str):
        self.id = call_id
        self.type = "function"
        self.function = GeminiFunction(function_name, arguments)


class GeminiFunction:
    """Function wrapper to match OpenAI format"""

    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments

    def model_dump(self):
        """Return dict representation"""
        return {"name": self.name, "arguments": self.arguments}


class GeminiResponse:
    """Response wrapper to match OpenAI format"""

    def __init__(self, response, model_name):
        self.id = f"gemini-{int(time.time())}"
        self.model = model_name
        self.created = int(time.time())

        # Extract text and tool calls
        self.choices = [GeminiChoice(response)]
        self.usage = GeminiUsage(response)

    def model_dump(self, *args, **kwargs):
        """Convert to dict for compatibility"""
        choice = self.choices[0]
        result = {
            "id": self.id,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": choice.message.content or "",
                    },
                    "finish_reason": choice.finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "model": self.model,
            "created": self.created,
        }

        # Add tool calls if present
        if choice.message.tool_calls:
            result["choices"][0]["message"]["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return result


def _convert_protobuf_to_dict(obj):
    """Recursively convert protobuf objects to Python dict/list"""
    if isinstance(obj, dict):
        return {k: _convert_protobuf_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_protobuf_to_dict(item) for item in obj]
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        # Handle protobuf RepeatedComposite and similar iterables
        return [_convert_protobuf_to_dict(item) for item in obj]
    elif hasattr(obj, "items"):
        # Handle dict-like objects
        return {k: _convert_protobuf_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        # Convert floats that are actually integers (like 0.0 -> 0)
        if obj.is_integer():
            return int(obj)
        return obj
    else:
        # Return primitive types as-is
        return obj


class GeminiMessage:
    """Message wrapper to match OpenAI format"""

    def __init__(self, response):
        self.role = "assistant"
        self.content = None
        self.tool_calls = None

        # Extract function calls and text from parts
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate.content, "parts"):
                tool_calls = []
                text_parts = []

                for part in candidate.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        call_id = f"call_{int(time.time())}_{len(tool_calls)}"

                        # Convert protobuf args to Python dict properly
                        args_dict = _convert_protobuf_to_dict(dict(fc.args))
                        args_json = json.dumps(args_dict)

                        tool_calls.append(
                            GeminiToolCall(
                                call_id=call_id,
                                function_name=fc.name,
                                arguments=args_json,
                            )
                        )
                    elif hasattr(part, "text") and part.text:
                        text_parts.append(part.text)

                if tool_calls:
                    self.tool_calls = tool_calls
                if text_parts:
                    self.content = "".join(text_parts)

        # Try to get text only if we don't have tool calls (to avoid the error)
        if not self.tool_calls and not self.content:
            try:
                if hasattr(response, "text"):
                    self.content = response.text
            except ValueError:
                # Response has function_call but no text
                pass


class GeminiChoice:
    """Choice wrapper to match OpenAI format"""

    def __init__(self, response):
        self.message = GeminiMessage(response)
        self.finish_reason = "stop"


class GeminiUsage:
    """Usage wrapper to match OpenAI format"""

    def __init__(self, response):
        if hasattr(response, "usage_metadata"):
            self.prompt_tokens = getattr(
                response.usage_metadata, "prompt_token_count", 0
            )
            self.completion_tokens = getattr(
                response.usage_metadata, "candidates_token_count", 0
            )
            self.total_tokens = getattr(response.usage_metadata, "total_token_count", 0)
        else:
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.total_tokens = 0


class GeminiChatCompletions:
    """Chat completions interface for Gemini"""

    def __init__(self, model_name: str):
        self.model_name = model_name

    def _convert_messages_to_gemini(self, messages: List[Dict[str, Any]]) -> tuple:
        """Convert OpenAI-style messages to Gemini format"""
        system_instruction = None
        history = []
        
        i = 0
        while i < len(messages) - 1:  # All except last message
            msg = messages[i]
            role = msg.get("role")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if role == "system":
                system_instruction = content
                i += 1
            elif role == "user":
                # Check if last history item is also user - if so, merge them
                if history and history[-1].get("role") == "user":
                    # Merge consecutive user messages
                    history[-1]["parts"].append(content)
                else:
                    # New user message
                    history.append({"role": "user", "parts": [content]})
                i += 1
            elif role == "assistant":
                # Handle assistant messages with tool calls
                if tool_calls:
                    # Convert tool calls to Gemini function calls
                    parts = []
                    
                    # Add text content if present
                    if content:
                        parts.append(content)
                    
                    # Add function calls
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        func_name = func.get("name", "")
                        func_args_str = func.get("arguments", "{}")
                        
                        # Parse arguments back to dict
                        try:
                            func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
                        except:
                            func_args = {}
                        
                        # Create Gemini function call part
                        parts.append(
                            genai.protos.Part(
                                function_call=genai.protos.FunctionCall(
                                    name=func_name,
                                    args=func_args
                                )
                            )
                        )
                    
                    history.append({"role": "model", "parts": parts})
                    
                    # Now collect ALL following tool responses into ONE user turn
                    function_responses = []
                    j = i + 1
                    while j < len(messages) - 1 and messages[j].get("role") == "tool":
                        tool_msg = messages[j]
                        tool_name = tool_msg.get("name", "")
                        tool_content = tool_msg.get("content", "")
                        
                        # Create function response part
                        function_responses.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": tool_content}
                                )
                            )
                        )
                        j += 1
                    
                    # Add all function responses in ONE user turn
                    if function_responses:
                        history.append({"role": "user", "parts": function_responses})
                    
                    # Skip past the tool messages we just processed
                    i = j
                else:
                    # Regular assistant message without tool calls
                    history.append({"role": "model", "parts": [content]})
                    i += 1
            elif role == "tool":
                # This should be handled in the assistant branch above
                # But if we hit a standalone tool message, skip it
                i += 1
            else:
                i += 1

        # Handle last message
        last_msg = messages[-1] if messages else {"role": "user", "content": ""}
        merged_into_history = False
        
        # If last message is user and previous history item is also user (with function_responses),
        # we need to combine them to avoid consecutive user turns
        if (last_msg.get("role") == "user" and 
            history and 
            history[-1].get("role") == "user"):
            # Check if last history has function_responses
            has_function_response = any(
                hasattr(p, 'function_response') for p in history[-1].get("parts", [])
            )
            if has_function_response:
                # Merge user text into the function_response turn
                user_text = last_msg.get("content", "")
                if user_text:
                    history[-1]["parts"].append(user_text)
                merged_into_history = True
            else:
                # Both are regular user messages - merge them
                user_text = last_msg.get("content", "")
                if user_text:
                    history[-1]["parts"].append(user_text)
                merged_into_history = True
        
        if merged_into_history:
            user_message = None  # Don't send separate message
        else:
            user_message = last_msg.get("content", "") or "."

        return system_instruction, history, user_message, merged_into_history

    def _convert_tools_to_gemini(self, tools: Optional[List[Dict]]) -> Optional[List]:
        """Convert OpenAI-style tools to Gemini function declarations"""
        if not tools:
            return None

        function_declarations = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                params = func.get("parameters", {})

                # Convert OpenAI schema to Gemini schema
                gemini_params = self._convert_schema_to_gemini(params)

                function_declarations.append(
                    genai.protos.FunctionDeclaration(
                        name=func.get("name"),
                        description=func.get("description", ""),
                        parameters=gemini_params,
                    )
                )

        return (
            [genai.protos.Tool(function_declarations=function_declarations)]
            if function_declarations
            else None
        )

    def _convert_schema_to_gemini(self, schema: Dict) -> Dict:
        """Convert OpenAI JSON schema to Gemini schema format"""
        if not schema:
            return {}

        # Fields that Gemini supports - filter out everything else
        supported_fields = [
            "type",
            "properties",
            "description",
            "required",
            "items",
            "enum",
            "default",
            "format",
        ]

        gemini_schema = {}

        # Convert type
        if "type" in schema:
            schema_type = schema["type"].upper()
            # Map OpenAI types to Gemini types
            type_mapping = {
                "OBJECT": "OBJECT",
                "STRING": "STRING",
                "NUMBER": "NUMBER",
                "INTEGER": "INTEGER",
                "BOOLEAN": "BOOLEAN",
                "ARRAY": "ARRAY",
            }
            gemini_schema["type"] = type_mapping.get(schema_type, "STRING")

        # Convert properties (recursive)
        if "properties" in schema:
            gemini_schema["properties"] = {}
            for prop_name, prop_schema in schema["properties"].items():
                gemini_schema["properties"][prop_name] = self._convert_schema_to_gemini(
                    prop_schema
                )

        # Convert description
        if "description" in schema:
            gemini_schema["description"] = schema["description"]

        # Convert required fields
        if "required" in schema:
            gemini_schema["required"] = (
                list(schema["required"])
                if not isinstance(schema["required"], list)
                else schema["required"]
            )

        # Convert items (for arrays)
        if "items" in schema:
            gemini_schema["items"] = self._convert_schema_to_gemini(schema["items"])

        # Convert enum
        if "enum" in schema:
            gemini_schema["enum"] = (
                list(schema["enum"])
                if not isinstance(schema["enum"], list)
                else schema["enum"]
            )

        # Note: Intentionally filtering out OpenAI-specific fields that Gemini doesn't support:
        # - additionalProperties
        # - dependencies
        # - minItems, maxItems
        # - minimum, maximum
        # - default (causes "Unknown field for Schema: default" error)
        # - format
        # These cause serialization errors in Gemini protobuf

        return gemini_schema

    async def _stream_response(self, response, model_name):
        """Convert Gemini response to streaming format"""
        # Gemini doesn't support true streaming in the same way as OpenAI
        # We'll simulate it by yielding the response as a single chunk

        class StreamChunk:
            def __init__(self, content):
                self.choices = [StreamChoice(content)]

        class StreamChoice:
            def __init__(self, content):
                self.delta = StreamDelta(content)

        class StreamDelta:
            def __init__(self, content):
                self.content = content

        # Get the full content
        content = ""
        if hasattr(response, "text"):
            try:
                content = response.text
            except ValueError:
                # Has function call, no text
                content = ""
        elif hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate.content, "parts"):
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        content += part.text

        # Yield the content as a single chunk (simulating streaming)
        yield StreamChunk(content)

    async def create(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Any] = None,
        stream: bool = False,
        **kwargs,
    ):
        """Create a chat completion (async)"""
        try:
            from app.logger import logger
            
            # Log incoming messages for debugging (use INFO so they're visible)
            logger.info(f"📨 Gemini receiving {len(messages)} messages")
            # Only log last 10 messages to avoid spam
            start_idx = max(0, len(messages) - 10)
            for i in range(start_idx, len(messages)):
                msg = messages[i]
                role = msg.get("role")
                has_content = bool(msg.get("content"))
                has_tool_calls = bool(msg.get("tool_calls"))
                tool_call_id = msg.get("tool_call_id")
                tool_name = msg.get("name")
                logger.info(
                    f"  Msg {i}: role={role}, has_content={has_content}, "
                    f"has_tool_calls={has_tool_calls}, tool_call_id={tool_call_id}, name={tool_name}"
                )
            
            # Convert messages
            system_instruction, history, user_message, merged_into_history = (
                self._convert_messages_to_gemini(messages)
            )
            
            logger.info(f"📝 Gemini history: {len(history)} messages, merged_last={merged_into_history}")
            # Only log last 10 history items
            start_idx = max(0, len(history) - 10)
            for i in range(start_idx, len(history)):
                h = history[i]
                parts_info = []
                for part in h.get('parts', []):
                    if isinstance(part, str):
                        parts_info.append(f"text({len(part)} chars)")
                    elif hasattr(part, 'function_call') and part.function_call:
                        fname = getattr(part.function_call, 'name', '?')
                        parts_info.append(f"function_call({fname})")
                    elif hasattr(part, 'function_response') and part.function_response:
                        fname = getattr(part.function_response, 'name', '?')
                        parts_info.append(f"function_response({fname})")
                    else:
                        parts_info.append(f"unknown({type(part).__name__})")
                logger.info(f"  History {i}: role={h.get('role')}, parts=[{', '.join(parts_info)}]")

            # Convert tools
            gemini_tools = self._convert_tools_to_gemini(tools)

            # Generation config
            gen_config = {
                "temperature": temperature if temperature is not None else 0.0,
                "max_output_tokens": max_tokens if max_tokens is not None else 8192,
            }

            # Create model
            model_kwargs = {"model_name": self.model_name}

            if system_instruction:
                model_kwargs["system_instruction"] = system_instruction

            if gemini_tools:
                model_kwargs["tools"] = gemini_tools

            model_instance = genai.GenerativeModel(**model_kwargs)

            # If message was merged into history, we need to use generate_content with full history
            # because send_message would create another user turn
            if merged_into_history and history:
                # Convert history to Gemini's Content format for generate_content
                contents = []
                for h in history:
                    role = "user" if h["role"] == "user" else "model"
                    contents.append({"role": role, "parts": h["parts"]})
                
                logger.info(f"🔄 Using generate_content (message merged into history)")
                response = await model_instance.generate_content_async(
                    contents, generation_config=gen_config
                )
            elif history:
                # Regular flow: history + new user message
                logger.info(f"🔄 Using start_chat + send_message")
                chat = model_instance.start_chat(history=history)
                response = await chat.send_message_async(
                    user_message, generation_config=gen_config
                )
            else:
                # No history, just send the message
                logger.info(f"🔄 Using generate_content (no history)")
                response = await model_instance.generate_content_async(
                    user_message, generation_config=gen_config
                )

            # Handle streaming vs non-streaming
            if stream:
                # Return async generator for streaming
                return self._stream_response(response, self.model_name)
            else:
                gemini_response = GeminiResponse(response, self.model_name)
                
                # Debug logging (use INFO so it's visible)
                msg = gemini_response.choices[0].message
                logger.info(
                    f"📤 Gemini response: "
                    f"has_content={bool(msg.content)}, "
                    f"has_tool_calls={bool(msg.tool_calls)}, "
                    f"num_tool_calls={len(msg.tool_calls) if msg.tool_calls else 0}"
                )
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        logger.info(f"  Tool call: {tc.function.name}")
                
                return gemini_response

        except Exception as e:
            from app.logger import logger

            logger.error(f"Gemini API error: {e}")
            raise


class GeminiChat:
    """Chat interface"""

    def __init__(self, model_name: str):
        self.completions = GeminiChatCompletions(model_name)


class GeminiClient:
    """Main Gemini client"""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ):
        genai.configure(api_key=api_key)
        self.model = model
        self.chat = GeminiChat(model)
