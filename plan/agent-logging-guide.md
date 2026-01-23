# Agent Logging Guide: Capturing Model Reasoning

## Overview
This guide shows how to add comprehensive logging to your agentic loop to track model reasoning, tool decisions, and execution flow.

## Key Areas to Log

### 1. **Model Reasoning & Thinking**
- What the model is trying to accomplish
- Why it chose specific tools
- Any constraints or considerations

### 2. **Tool Decisions**
- Which tool the agent selected
- Arguments passed to the tool
- Tool execution results

### 3. **Conversation State**
- Message flow and context
- Turn count and loop status
- Error handling

### 4. **Performance Metrics**
- Token usage and costs
- Latency per turn
- Success/failure rates

## Implementation Patterns

### Pattern 1: Structured Logging with Context

```python
import logging
import json
from typing import Any
from datetime import datetime
from uuid import uuid4

# Setup structured logger
logger = logging.getLogger("agent")
handler = logging.FileHandler("agent_reasoning.log")
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class ReasoningLogger:
    """Structured logging for agent reasoning"""
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id or str(uuid4())
        self.turn_count = 0
    
    def log_user_input(self, prompt: str):
        """Log the incoming user prompt"""
        logger.info(f"[{self.session_id}] User input: {prompt}")
    
    def log_api_request(self, messages: list[dict]):
        """Log the messages being sent to the model"""
        logger.debug(f"[{self.session_id}] API request with {len(messages)} messages")
        # Only log system message and latest user message for brevity
        if messages:
            logger.debug(f"[{self.session_id}] Latest message: {messages[-1]}")
    
    def log_model_response(self, response: Any, model: str):
        """Log the raw model response"""
        self.turn_count += 1
        
        msg = response.choices[0].message
        assistant_content = msg.content or ""
        tool_calls = list(getattr(msg, "tool_calls", None) or [])
        
        logger.info(f"[{self.session_id}] Turn {self.turn_count}: Model response")
        
        if assistant_content:
            logger.info(f"[{self.session_id}] Assistant reasoning: {assistant_content}")
        
        logger.info(f"[{self.session_id}] Tool calls requested: {len(tool_calls)}")
        
        # Log token usage if available
        if hasattr(response, 'usage'):
            logger.info(
                f"[{self.session_id}] Token usage - "
                f"Input: {response.usage.prompt_tokens}, "
                f"Output: {response.usage.completion_tokens}"
            )
    
    def log_tool_selection(self, tool_name: str, arguments: dict):
        """Log when the model selects a tool"""
        logger.info(
            f"[{self.session_id}] Tool selected: {tool_name} "
            f"with args: {json.dumps(arguments, indent=2)}"
        )
    
    def log_tool_execution(self, tool_name: str, result: str, error: bool = False):
        """Log tool execution results"""
        level = logging.ERROR if error else logging.INFO
        logger.log(
            level,
            f"[{self.session_id}] Tool '{tool_name}' result: {result[:200]}"
        )
    
    def log_loop_completion(self, reason: str):
        """Log why the agent loop ended"""
        logger.info(
            f"[{self.session_id}] Loop completed after {self.turn_count} turns. "
            f"Reason: {reason}"
        )
```

### Pattern 2: Enhanced Agent Loop with Logging

```python
def run_agent_loop(prompt: str, history: list[dict[str, Any]]) -> None:
    """Run the agent loop with comprehensive reasoning logging"""
    
    reasoning_logger = ReasoningLogger()
    
    if not prompt.strip():
        return
    
    reasoning_logger.log_user_input(prompt)
    history.append({"role": "user", "content": prompt})
    
    for turn in range(settings.MAX_TURNS):
        messages: Any = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
        ]
        
        reasoning_logger.log_api_request(messages)
        
        try:
            resp = client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=messages,
                tools=cast(Any, TOOLS),
            )
        except Exception as e:
            logger.error(f"[{reasoning_logger.session_id}] API error: {e}")
            raise
        
        # Parse response
        msg = resp.choices[0].message
        assistant_content = msg.content or ""
        tool_calls: list[Any] = list(getattr(msg, "tool_calls", None) or [])
        
        # Log the model's reasoning and response
        reasoning_logger.log_model_response(resp, settings.DEFAULT_MODEL)
        
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": assistant_content,
        }
        if tool_calls:
            assistant_message["tool_calls"] = [tc.model_dump() for tc in tool_calls]
        history.append(assistant_message)
        
        if assistant_content:
            print(assistant_content)
        
        # No tool calls means we're done
        if not tool_calls:
            reasoning_logger.log_loop_completion("No more tool calls requested")
            return
        
        # Process each tool call
        for tc in tool_calls:
            tc_any = tc
            if getattr(tc_any, "type", None) != "function":
                continue
            
            fn = tc_any.function
            fn_name = getattr(fn, "name", None)
            
            if not isinstance(fn_name, str) or fn_name not in AVAILABLE_TOOLS:
                error_msg = f"Unknown tool: {fn_name}"
                logger.error(f"[{reasoning_logger.session_id}] {error_msg}")
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_any.id,
                        "content": error_msg,
                    }
                )
                continue
            
            try:
                arguments_raw = getattr(fn, "arguments", None) or "{}"
                arguments_any = json.loads(arguments_raw)
            except (TypeError, json.JSONDecodeError) as e:
                arguments_any = {}
                logger.error(
                    f"[{reasoning_logger.session_id}] "
                    f"Failed to parse arguments for {fn_name}: {e}"
                )
            
            if isinstance(arguments_any, dict):
                arguments = cast(dict[str, Any], arguments_any)
            else:
                arguments = {}
            
            # Log tool selection
            reasoning_logger.log_tool_selection(fn_name, arguments)
            
            # Execute tool
            try:
                tool_output = run_tool(fn_name, arguments)
                reasoning_logger.log_tool_execution(fn_name, tool_output, error=False)
            except Exception as e:
                tool_output = str(e)
                reasoning_logger.log_tool_execution(fn_name, tool_output, error=True)
            
            # Add tool result to history
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_any.id,
                    "content": tool_output,
                }
            )
        
        # Safety check: max turns
        if turn == settings.MAX_TURNS - 1:
            reasoning_logger.log_loop_completion(f"Reached max turns ({settings.MAX_TURNS})")
```

## Log Output Example

```
2026-01-23 14:09:15,234 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] User input: What's the weather in Sofia?
2026-01-23 14:09:15,456 - agent - DEBUG - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] API request with 2 messages
2026-01-23 14:09:15,678 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Turn 1: Model response
2026-01-23 14:09:15,789 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Assistant reasoning: I need to check the current weather in Sofia. Let me use the weather tool.
2026-01-23 14:09:15,901 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Tool calls requested: 1
2026-01-23 14:09:15,923 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Token usage - Input: 145, Output: 89
2026-01-23 14:09:16,012 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Tool selected: get_weather with args: {"city": "Sofia", "units": "celsius"}
2026-01-23 14:09:16,234 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Tool 'get_weather' result: {"temperature": 8, "condition": "cloudy", "humidity": 65}
2026-01-23 14:09:16,456 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Turn 2: Model response
2026-01-23 14:09:16,567 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Assistant reasoning: Perfect! I have the weather information. The weather in Sofia is cloudy with a temperature of 8°C.
2026-01-23 14:09:16,678 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Tool calls requested: 0
2026-01-23 14:09:16,789 - agent - INFO - [a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d] Loop completed after 2 turns. Reason: No more tool calls requested
```

## Advanced Logging Features

### JSON-Structured Logging

For better analysis, use JSON structured logging:

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": getattr(record, "session_id", None),
            "turn": getattr(record, "turn", None),
        }
        return json.dumps(log_obj)

# Use in logging setup
json_handler = logging.FileHandler("agent_reasoning.jsonl")
json_handler.setFormatter(JSONFormatter())
logger.addHandler(json_handler)
```

### Performance Metrics

```python
import time

class PerformanceLogger:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.timings = {}
    
    def start_timer(self, key: str):
        self.timings[key] = {"start": time.time()}
    
    def end_timer(self, key: str):
        if key in self.timings:
            self.timings[key]["duration"] = time.time() - self.timings[key]["start"]
            duration_ms = self.timings[key]["duration"] * 1000
            logger.info(f"[{self.session_id}] {key} took {duration_ms:.2f}ms")
    
    def log_cost_estimate(self, input_tokens: int, output_tokens: int, model: str):
        """Estimate and log API costs"""
        # Example pricing (adjust for your model/region)
        input_cost_per_1k = 0.00150  # GPT-4o
        output_cost_per_1k = 0.00600
        
        total_cost = (input_tokens * input_cost_per_1k + 
                      output_tokens * output_cost_per_1k) / 1000
        logger.info(
            f"[{self.session_id}] Estimated cost: ${total_cost:.4f} "
            f"({input_tokens} in, {output_tokens} out)"
        )
```

## Best Practices

1. **Use Session IDs**: Correlate all logs for a single conversation with a unique ID
2. **Structured Logging**: Use JSON format for easier machine parsing and analysis
3. **Sensitive Data**: Avoid logging API keys, user PII, or sensitive prompts
4. **Log Levels**: Use DEBUG for detailed traces, INFO for milestones, ERROR for failures
5. **Sampling**: In production, consider sampling 10-20% of logs to reduce costs
6. **Centralized Collection**: Use a service like CloudWatch, DataDog, or Splunk to aggregate logs
7. **Metrics**: Track success rates, average turns, token usage, and costs
