# Plan: Adding Tool Calling to PersonaPlex 7B

This document outlines how to add **tool calling** (function calling) to the PersonaPlex 7B speech-to-speech model. The model does not natively support tool calls; this plan uses **prompt-based structured output** plus server-side parsing and execution, with optional protocol and client updates.

---

## 1. Current Architecture Summary

### 1.1 Stack
- **Model**: PersonaPlex 7B (Moshi-based), full-duplex speech-to-speech.
- **Server**: `moshi/moshi/server.py` — loads Mimi (audio codec), LM (language model), SentencePiece text tokenizer (`tokenizer_spm_32k_3.model`, 32k vocab).
- **Inference**: `LMGen.step()` consumes one frame of user audio codes and produces one **text token** (stream 0) plus **audio tokens** (streams 1..dep_q). Text is decoded with `text_tokenizer.id_to_piece()` and sent to the client token-by-token.
- **Prompting**: System prompt is passed as `text_prompt` (query param), wrapped in `<system> ... <system>` and tokenized into `lm_gen.text_prompt_tokens`, then forced into the model during `step_system_prompts_async()` before the conversation loop.

### 1.2 Protocol (WebSocket binary)
| Byte 0 | Meaning    | Payload              |
|--------|------------|----------------------|
| `0x00` | Handshake  | version, model       |
| `0x01` | Audio      | Opus bytes            |
| `0x02` | Text       | UTF-8 decoded text   |
| `0x03` | Control    | start / endTurn / …   |
| `0x04` | Metadata   | JSON                  |
| `0x05` | Error      | UTF-8 message         |
| `0x06` | Ping       | —                     |

Connection: client sends `text_prompt` and `voice_prompt` as query params; server sends handshake then streams audio (0x01) and text (0x02) in real time.

### 1.3 Relevant Code Paths
- **Server chat loop**: `server.py` → `handle_chat` → `opus_loop()`: each step calls `lm_gen.step(codes)`, then sends one text token as `b"\x02" + bytes(_text, "utf8")` when `text_token not in (0, 3)` (EPAD/PAD).
- **Text generation**: `lm.py` → `LMGen.step()` → `process_transformer_output()` → `sample_token(text_logits, …)` for next text token; token is written to streaming cache and returned.
- **System prompt**: Applied in `handle_chat` via `lm_gen.text_prompt_tokens = text_tokenizer.encode(wrap_with_system_tags(request.query["text_prompt"]))`.

---

## 2. What “Tool Calling” Means Here

- **Goal**: The assistant can “call” named tools with arguments (e.g. `get_weather(city="Paris")`), the server executes them, and optionally uses results in the conversation (e.g. speak the answer or continue with context).
- **Constraint**: The 7B model is **not** trained for tool calls. We avoid changing model weights in the base plan and rely on:
  - **Structured output via system prompt**: Instruct the model to emit a specific format when it wants to call a tool (e.g. `<tool_call>{"name":"...","arguments":{}}</tool_call>`).
  - **Server-side parsing**: Buffer streaming text, detect the format, parse JSON, dispatch to a tool registry, and optionally inject results.

Optional later steps: fine-tune the model for tool format, or add a small classifier to detect “tool intent” and route to a separate text/API layer.

---

## 3. High-Level Approach

1. **Define a tool-call format** (e.g. a single line or block the model is asked to output).
2. **Extend the system prompt** so the model is instructed to use that format when it needs to call a tool; document tool names and arguments in the prompt.
3. **Server: text buffer and parser** — In the same loop where we currently send each text token (or chunk) to the client, accumulate into a session buffer; when we see the end of a tool-call block (e.g. `</tool_call>`), parse it and dispatch.
4. **Server: tool registry and execution** — Register Python callables (or safe stubs) for each tool; execute in an async/sync worker; optionally pass results back into the conversation (e.g. by injecting a “tool result” line the model can condition on in a follow-up turn, or by sending a separate message to the client).
5. **Protocol and client (optional)** — Add message types for tool definitions (client → server), tool_call (server → client), and tool_result (client → server or server → client) so the UI can show “calling X” and “result: Y” and so the client can send tool definitions per session.

---

## 4. Implementation Phases

### Phase 1: Server-Side Text Buffer and Tool-Call Parsing (no protocol change)

**Objective**: Detect and parse tool calls from the existing streaming text without changing the WebSocket protocol.

**Steps**:
1. **Tool-call format**  
   Choose a format that is parseable from a stream and easy to describe in a prompt, e.g.:
   - Option A: Single-line JSON between delimiters:  
     `\n<tool_call>{"name":"get_weather","arguments":{"city":"Paris"}}</tool_call>\n`
   - Option B: Multi-line with closing tag:  
     `<tool_call>\n{"name":"...", "arguments":{...}}\n</tool_call>`

   Prefer a **single-line** variant so that we can flush the buffer on newline and avoid holding too much text in memory.

2. **Buffer in `opus_loop()`**  
   In `server.py`, instead of sending every token immediately as `b"\x02" + _text`:
   - Append `_text` to a **session text buffer** (e.g. `agent_text_buffer: list[str]` or a single string).
   - Optionally still send the same bytes to the client for display (so the UI shows the raw stream), or send only “non-tool” segments after parsing (see below).
   - When the buffer contains a complete tool call (e.g. line containing `</tool_call>` or a full line matching `<tool_call>...</tool_call>`), extract that line, parse JSON, and pass to a small **tool handler** (Phase 2). Remove the parsed segment from the buffer and do **not** send the raw tool-call text to the client (or send a substitute like “(calling get_weather…)”) if you want to hide implementation details.

3. **Parsing and validation**  
   - New module: `moshi/moshi/tool_calling.py` (or `tools.py`).
   - Functions: `parse_tool_call_from_line(line: str) -> Optional[ToolCall]`, `ToolCall = TypedDict with name, arguments`.
   - Validate `name` against an allowed list and `arguments` against a minimal schema (e.g. required keys) to avoid injection.

4. **Integration point in `server.py`**  
   - In `opus_loop()`, after decoding `text_token` to `_text`, append to buffer; then call a helper e.g. `process_text_buffer(buffer, ws, tool_registry)` that:
     - Flushes complete lines that are **not** tool calls to the client (as 0x02 messages).
     - When a complete tool call is found, parses it, runs the tool (Phase 2), and then either sends a replacement phrase to the client or a special message (Phase 3).

**Deliverables**:
- `moshi/moshi/tool_calling.py`: format spec, `parse_tool_call_from_line()`, `ToolCall` type.
- `server.py`: session buffer, call to parser and (in Phase 2) executor; decision on what to send to client for tool-call lines.

---

### Phase 2: Tool Registry and Execution

**Objective**: Register tools and execute them safely when a parsed tool call is found.

**Steps**:
1. **Registry**  
   In `tool_calling.py` (or `tools.py`): maintain a `ToolRegistry` (e.g. `dict[str, Callable]` or a small class with `register(name, fn, schema)`). Default tools can be stubs that return fixed strings (e.g. “Weather in Paris: 20°C”) for testing.

2. **Execution**  
   - `execute_tool(name: str, arguments: dict) -> str` (or a structured result). Run in a thread pool or async task so the main loop is not blocked for long. Timeout and size limits on arguments/result to avoid abuse.
   - If execution fails, return a fixed message (e.g. “Tool error: …”) so the model or UI can react.

3. **Result handling**  
   - **Option A (simple)**: Append the tool result as a single “assistant” text line in the session (e.g. in a buffer that will be sent to the client as 0x02). No change to model state.
   - **Option B (richer)**: Store “last tool result” and inject it into the **next** user turn or system context (would require a way to feed text back into the model; see “Injecting tool results into the model” below).
   - For Phase 2, Option A is enough: send the tool result as one or more 0x02 text messages so the client displays it.

4. **Security**  
   - Only allow tools that are explicitly registered.
   - Validate arguments (type, allowed keys) per tool.
   - Do not pass unsanitized user input to shell or file system; prefer pure Python implementations or tightly controlled APIs.

**Deliverables**:
- `tool_calling.py`: `ToolRegistry`, `execute_tool()`, 1–2 example tools (e.g. `get_weather`, `get_time`).
- `server.py`: after parsing a tool call, call `execute_tool()` and send the result as 0x02 (and optionally suppress sending the raw `<tool_call>...` line).

---

### Phase 3: Protocol and Client Updates (Optional)

**Objective**: Allow the client to send tool definitions and display tool calls and results explicitly.

**Steps**:
1. **New message types** (extend `client/src/protocol/types.ts` and encoder/decoder):
   - **Tool definitions (client → server)**  
     e.g. `0x07`: payload = JSON `{ "tools": [ { "name", "description", "parameters" } ] }`. Server uses this to build the system prompt snippet for “available tools” and to validate incoming tool calls.
   - **Tool call (server → client)**  
     e.g. `0x08`: payload = JSON `{ "name", "arguments" }`. Client can show “Calling get_weather(…)”.
   - **Tool result (server → client)**  
     e.g. `0x09`: payload = JSON or string `{ "result": "..." }`. Client can show “Result: …”.

2. **Server**  
   - In `recv_loop()`, handle new message type (e.g. 0x07) and update session state: store tool list and optionally regenerate or append to `text_prompt` for this session (if you support per-session system prompt).
   - When a tool call is parsed, send 0x08 (tool call) then after execution 0x09 (tool result); still send 0x02 for any spoken reply or for the result text if you want it in the same transcript.

3. **Client**  
   - Decode 0x08 and 0x09 in `encoder.ts`.
   - In Conversation UI, display tool calls and results (e.g. collapsible “Tool: get_weather → 20°C”).
   - Optional: add a “tools” field to the connection config (or a JSON blob in query params) and send 0x07 on connect so the server knows which tools to allow and how to describe them in the prompt.

**Deliverables**:
- Updated `protocol/types.ts`, `encoder.ts` (encode/decode new types).
- `server.py`: send 0x08/0x09; accept 0x07 and use tool list for prompt/validation.
- Client Conversation page: show tool call and tool result in the transcript or a side panel.

---

### Phase 4: Improving Reliability (Optional)

The base model may not reliably output `<tool_call>...</tool_call>` or valid JSON. Options:

1. **Prompt engineering**  
   - Add few-shot examples in the system prompt: “When you need to call a tool, output exactly one line: <tool_call>{"name":"...","arguments":{...}}</tool_call>”.
   - Keep the list of tools and their arguments short and consistent.

2. **Structured output / grammar**  
   - If the tokenizer and model support it, constrain decoding (e.g. only allow tokens that keep the sequence valid for a JSON schema). This would require changes in `lm.py` (e.g. masking logits in `sample_token`). Likely non-trivial with SentencePiece and the current streaming setup.

3. **Fine-tuning**  
   - Collect or synthesize (text, audio) data where the assistant outputs the tool format; fine-tune the PersonaPlex (or text head) to emit tool calls more consistently. Out of scope for the initial plan but documented as a future path.

4. **Hybrid with a text LLM**  
   - Use the 7B model for voice and a separate text LLM (e.g. small open-weight) for “intent + tool call” from the same user turn; then execute the tool and feed the result to PersonaPlex for the spoken reply. Increases latency and complexity but can be more accurate for tools.

---

## 5. Injecting Tool Results Into the Model (Optional)

Today the model only gets:
- System prompt (once at start),
- Live user audio (streamed).

To make the assistant “aware” of the tool result in the same turn, you’d need to feed text (or a representation of it) back into the model. Options:

- **Text injection as “fake” user turn**: After executing the tool, treat the result as a “user” message and run a short TTS or a text-only “user” segment. That would require either:
  - A separate TTS to turn “Result: 20°C” into audio and feed it as user audio, or
  - A way to feed **text** as if it were user input (current pipeline is audio → Mimi → codes → LM). So you’d need a path: text → tokenize → inject as “user” text tokens. The current code path does not support injecting arbitrary user text tokens in the middle of the stream; only system prompt is forced.
- **Next turn**: Simpler approach: send the tool result to the client only (0x02 or 0x09). The user (or an automated client) can then speak or type “What was the weather?” and the model answers from context of the displayed result, or the client could send a **synthetic** user message (if you later add a “text input” channel) that includes the tool result so the next model reply is conditioned on it.

For a first version, **no injection** is recommended: just show the tool result to the user and optionally mention in the system prompt that “when you call a tool, the result will be shown to the user.”

---

## 6. Suggested File and Code Touchpoints

| Area | File(s) | Changes |
|------|---------|--------|
| Tool format & parsing | **New** `moshi/moshi/tool_calling.py` | `ToolCall` type, `parse_tool_call_from_line()`, `ToolRegistry`, `execute_tool()` |
| Server loop | `moshi/moshi/server.py` | Session text buffer in `opus_loop()`; after each text token, append and call buffer processor; on complete tool call → parse, execute, send result (0x02 or 0x09) |
| System prompt | `server.py` (and docs) | Document how to add “Available tools: …” and “Output format: <tool_call>...</tool_call>” to `text_prompt`; optional: build this from tool list if Phase 3 |
| Protocol | `client/src/protocol/types.ts`, `encoder.ts` | New message types 0x07, 0x08, 0x09 if Phase 3 |
| Client UI | `client/src/pages/Conversation/`, hooks | Decode and display tool_call / tool_result |
| Offline script | `moshi/moshi/offline.py` | Optional: same buffer/parser so offline runs can also detect and log (or stub) tool calls |

---

## 7. Testing Strategy

1. **Unit tests**  
   - `parse_tool_call_from_line()` with valid/invalid lines and malformed JSON.
   - `execute_tool()` with a mock registry and timeout/error cases.

2. **Integration**  
   - Start server with a stub tool (e.g. `get_time` returning a fixed string). Use a client that sends a `text_prompt` instructing the model to “at some point output <tool_call>{"name":"get_time","arguments":{}}</tool_call>”. Manually or with a script, send audio (or consider a text-only test path if added) and verify the server parses the tool call and sends the result.

3. **E2E**  
   - Full duplex: user says “What time is it?” (or a prompt that encourages the model to emit the tool format); check that the buffer eventually contains the tool call and that the client receives the result.

---

## 8. Summary

- **Phase 1**: Buffer streaming text in the server; parse a agreed `<tool_call>...</tool_call>` format; no protocol change.
- **Phase 2**: Tool registry and safe execution; send result as normal text (0x02).
- **Phase 3**: Optional new WebSocket message types and client UI for tool definitions and tool call/result.
- **Phase 4**: Optional improvements (prompt engineering, fine-tuning, or hybrid with a text LLM) for more reliable tool output.

This keeps the PersonaPlex 7B model unchanged and adds tool calling as a **server-side layer** on top of the existing streaming text output.
