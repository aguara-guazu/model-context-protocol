# MCP Tool Chaining Demo

Esta demostración muestra cómo funciona **Tool Chaining** en MCP con el **enfoque correcto**: el LLM decide automáticamente cuándo y cómo encadenar tools.

## ⚠️ Concepto Importante

**EL LLM DECIDE, NO EL DESARROLLADOR**

Tool chaining NO es algo que el desarrollador programa. El servidor expone:
1. Sus herramientas normales (fetch_user_data, analyze_sentiment, etc.)
2. Una herramienta especial `chain_tools` que explica al LLM cómo encadenar

El LLM recibe TODAS las herramientas y **decide por sí mismo** si:
- Usar herramientas individuales, o
- Encadenarlas usando `chain_tools`

El desarrollador NO escribe código para armar chains. Solo usa MCP normalmente.

## 📁 Contenido

- **`server.py`**: Servidor MCP con 6 herramientas + `chain_tools`
- **`test_llm_decides.py`**: ✅ **Prueba CORRECTA** donde Claude decide qué hacer
- **`old_incorrect_tests/`**: ❌ Pruebas incorrectas (no usar como ejemplo)

## 🛠️ Herramientas Disponibles

El servidor expone 7 herramientas vía MCP:

### 1. `chain_tools` (Herramienta Especial)
El LLM usa esta herramienta cuando decide que quiere encadenar múltiples operaciones.

**Descripción que recibe el LLM:**
```
Execute multiple tools in sequence with automatic reference resolution.

This tool allows you to chain multiple tool calls together. Results from earlier steps
can be referenced in later steps using dot notation (e.g., "step1.field" or just "step1"
for the whole object).

Example chain to fetch a user and analyze their bio:
{
  "chain": [
    {
      "tool": "fetch_user_data",
      "id": "user",
      "params": {"user_id": "user123"}
    },
    {
      "tool": "analyze_sentiment",
      "id": "sentiment",
      "params": {
        "text": "user.bio",
        "detailed": false
      }
    }
  ],
  "returnFormat": "final_only"
}

Reference syntax:
- "stepId.field" - Access a specific field from a previous step's result
- "stepId" - Use the entire result object from a previous step
- Nested fields: "step1.metrics.followers"
```

### 2-7. Herramientas de Negocio

- **`fetch_user_data`** - Obtiene datos de usuario
- **`analyze_sentiment`** - Analiza sentimiento de texto
- **`translate_text`** - Traduce texto
- **`generate_summary`** - Genera resúmenes
- **`calculate_metrics`** - Calcula métricas
- **`format_report`** - Formatea reportes

## 🚀 Cómo Ejecutar la Prueba Correcta

### Requisitos

```bash
# Instalar MCP SDK
pip install -e .

# Instalar dependencias del cliente
pip install httpx
```

### Configurar API Key

```bash
export ANTHROPIC_API_KEY="tu_api_key_aqui"
```

### Ejecutar

```bash
python examples/bedrock_chain_demo/test_llm_decides.py
```

## 📊 Qué Hace la Prueba Correcta

```
1. Conecta al servidor MCP
2. Hace list_tools() y obtiene las 7 herramientas
3. Pasa TODAS las herramientas a Claude
4. Le pregunta a Claude: "Fetch user data for user123, analyze sentiment,
   and calculate metrics"
5. Claude DECIDE qué hacer:
   - Opción A: Llamar 3 herramientas individuales
   - Opción B: Llamar chain_tools con un chain de 3 pasos
6. Ejecuta lo que Claude decidió
7. Muestra los resultados
```

## 🎯 Ejemplo de Salida

```
================================================================================
REAL TEST: Claude Decides Whether to Chain Tools
================================================================================

📋 Step 1: Getting tools from MCP server...
✅ Received 7 tools from server:
  - chain_tools: Execute multiple tools in sequence with automatic reference...
  - fetch_user_data: Fetch complete user profile data including bio, posts...
  - analyze_sentiment: Analyze sentiment of text and return positive/negative...
  - translate_text: Translate text from one language to another
  - generate_summary: Generate a concise summary from longer text
  - calculate_metrics: Calculate various metrics and statistics from user data
  - format_report: Format various data into a structured markdown report

🤖 Step 2: Asking Claude to perform a multi-step task...
Question: I need you to fetch user data for user123, analyze the sentiment of
their bio, and calculate their engagement metrics. Please help me with this.

📥 Claude's response:
Stop reason: tool_use

🔧 Claude decided to use 1 tool call(s):

  [1] Tool: chain_tools
     🎉 CLAUDE CHOSE TO CHAIN TOOLS!
     Chain has 3 steps:
       1. user: fetch_user_data <- {'user_id': 'user123'}
       2. sentiment: analyze_sentiment <- {'text': 'user.bio', 'detailed': False}
       3. metrics: calculate_metrics <- {'user_data': 'user'}

⚙️  Step 3: Executing Claude's tool calls...
Executing tool: chain_tools
INFO: 🔗 Executing chain with 3 steps
INFO:   → Step executing tool: fetch_user_data
INFO:   → Step executing tool: analyze_sentiment
INFO:   → Step executing tool: calculate_metrics
✅ chain_tools completed

📊 Chain Execution Results:
   Status: success
   Steps executed: 3
     ✅ user: success (3.45ms)
     ✅ sentiment: success (2.78ms)
     ✅ metrics: success (1.89ms)

   Final Result:
   {
     "engagement_score": 30.9,
     "activity_level": "medium",
     "follower_ratio": 0.75,
     "total_posts": 3
   }

🤖 Step 4: Getting Claude's final response...

💬 Claude's Final Answer:
I've successfully fetched the user data and completed the analysis! Here's what I found:

**User: Alice Johnson**

**Sentiment Analysis of Bio:**
- Sentiment: Positive
- Confidence: 67%
- The user's bio shows enthusiasm about technology and learning

**Engagement Metrics:**
- Engagement Score: 30.9
- Activity Level: Medium
- Follower Ratio: 0.75
- Total Posts: 3

The user appears to be moderately active with a positive outlook!

================================================================================
✅ TEST COMPLETE
================================================================================
```

## 🔑 Puntos Clave

1. **El desarrollador NO programa chains**: Solo expone herramientas vía MCP
2. **El LLM decide**: Recibe todas las tools y elige qué hacer
3. **chain_tools es una tool más**: Con descripción clara para el LLM
4. **Transparente**: El cliente solo ejecuta lo que el LLM pide
5. **Flexible**: El LLM puede usar tools individuales O chain_tools

## ❌ Qué NO Hacer

```python
# ❌ MAL - El desarrollador arma la chain
chain = [
    ChainStep(tool="fetch_user_data", id="user", params={"user_id": "user123"}),
    ChainStep(tool="analyze_sentiment", id="sentiment", params={"text": "user.bio"})
]
result = await execute_chain(chain)
```

```python
# ✅ BIEN - El LLM decide
tools = await mcp_session.list_tools()  # Incluye chain_tools
response = await claude_api(tools=tools, message="Analyze user123")
# Claude decide si usar chain_tools o tools individuales
if response.tool_use.name == "chain_tools":
    # El LLM construyó la chain, nosotros solo ejecutamos
    result = await mcp_session.call_tool("chain_tools", response.tool_use.input)
```

## 🏗️ Cómo Implementar en Tu Servidor

Para que tu servidor MCP soporte tool chaining:

### 1. Expón chain_tools como una tool normal

```python
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="chain_tools",
            description="Execute multiple tools in sequence... [explicación detallada]",
            inputSchema={
                "type": "object",
                "properties": {
                    "chain": {
                        "type": "array",
                        "items": {...}  # Schema de ChainStep
                    },
                    "returnFormat": {...}
                }
            }
        ),
        # ... tus otras tools
    ]
```

### 2. Maneja la llamada a chain_tools

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> dict:
    if name == "chain_tools":
        # Usar ChainExecutor del MCP SDK
        from mcp.server.lowlevel.chain import ChainExecutor, ChainValidator

        chain_steps = [types.ChainStep(**step) for step in arguments["chain"]]

        validator = ChainValidator(server._tool_cache)
        validator.validate_chain(chain_steps)

        executor = ChainExecutor(server._tool_cache, tool_executor_func)
        result = await executor.execute_chain(
            chain_steps,
            arguments.get("returnFormat", "final_only"),
            arguments.get("timeout")
        )
        return result

    # ... manejar tus otras tools
```

### 3. Listo!

El LLM automáticamente verá chain_tools en la lista de herramientas y decidirá cuándo usarla.

## 📚 Recursos

- [Documentación de Tool Chaining](../../docs/tool_chaining.md)
- [Tests Unitarios](../../tests/server/test_tool_chaining.py)
- [Propuesta Original (MEP)](../../PROPOSAL.md)

## 💡 Preguntas Frecuentes

**P: ¿El desarrollador del servidor necesita saber sobre chains?**
R: No. Solo expone `chain_tools` como una tool más. El MCP SDK maneja todo.

**P: ¿El desarrollador del cliente necesita saber sobre chains?**
R: No. Solo ejecuta las tool calls que el LLM solicita, igual que siempre.

**P: ¿Cuándo el LLM decide usar chain_tools vs tools individuales?**
R: El LLM decide basándose en la tarea. Si necesita pasar datos entre tools,
probablemente use chain_tools. Si son operaciones independientes, usará tools individuales.

**P: ¿Puedo forzar al LLM a usar chain_tools?**
R: Puedes sugerirlo en el prompt, pero la decisión final es del LLM.

**P: ¿Funciona con cualquier modelo?**
R: Cualquier modelo que soporte function calling y sepa seguir instrucciones complejas.
Claude 3.5 Sonnet/Haiku funcionan muy bien.
