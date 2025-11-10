# MCP Tool Chaining Demo with AWS Bedrock

Este directorio contiene una demostración completa de la funcionalidad de **Tool Chaining** en MCP, con un cliente que usa Claude Sonnet 4.5 a través de AWS Bedrock.

## 📁 Contenido

- **`server.py`**: Servidor MCP con 6 herramientas que soportan chaining
- **`client_bedrock.py`**: Cliente que usa AWS Bedrock para probar el servidor
- **`manual_test.py`**: Script para pruebas manuales sin AWS
- **`README.md`**: Esta documentación

## 🛠️ Herramientas Disponibles

El servidor proporciona 6 herramientas que pueden encadenarse:

1. **`fetch_user_data`** - Obtiene datos completos de un usuario
   - Input: `user_id`
   - Output: `{id, name, email, bio, posts, language, metrics}`

2. **`analyze_sentiment`** - Analiza el sentimiento de un texto
   - Input: `text`, `detailed` (optional)
   - Output: `{overall_sentiment, confidence, positive_score, negative_score}`

3. **`translate_text`** - Traduce texto entre idiomas
   - Input: `text`, `source_lang`, `target_lang`
   - Output: `{original_text, translated_text, source_lang, target_lang}`

4. **`generate_summary`** - Genera un resumen conciso
   - Input: `text`, `max_length` (optional)
   - Output: `{summary, word_count, compression_ratio}`

5. **`calculate_metrics`** - Calcula métricas de usuario
   - Input: `user_data`, `include_engagement_score` (optional)
   - Output: `{engagement_score, activity_level, follower_ratio, total_posts}`

6. **`format_report`** - Formatea datos en un reporte markdown
   - Input: `user_name`, `sentiment`, `metrics`, `summary` (optional)
   - Output: `{report, sections}`

## 🚀 Configuración

### 1. Instalar dependencias

```bash
# Desde la raíz del proyecto
cd /home/user/model-context-protocol

# Instalar el SDK de MCP
pip install -e .

# Instalar boto3 para AWS Bedrock
pip install boto3
```

### 2. Configurar AWS Credentials

```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_REGION="us-east-1"

# O configurar con AWS CLI
aws configure
```

### 3. Verificar acceso a Bedrock

Asegúrate de tener acceso al modelo Claude Sonnet 4.5:
- Model ID: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- Región: `us-east-1` (o tu región configurada)

## 📊 Ejecutar las Pruebas

### Opción 1: Demostración Simple (Recomendado para empezar)

```bash
# No requiere dependencias adicionales
python examples/bedrock_chain_demo/simple_test.py
```

Esta demostración muestra cómo funciona el tool chaining con un mock simple:
- ✅ Resolución de referencias (`"step1.field"`)
- ✅ Cadenas de 2 y 4 pasos
- ✅ Generación de reportes
- ✅ No requiere instalar dependencias

### Opción 2: Prueba Completa con MCP (Requiere uv)

```bash
# Desde la raíz del proyecto
cd /home/user/model-context-protocol
uv run python examples/bedrock_chain_demo/manual_test.py
```

Esto ejecutará pruebas completas contra el servidor MCP real:
1. **Test 1**: Llamada a una sola herramienta
2. **Test 2**: Cadena simple (Fetch → Analyze)
3. **Test 3**: Cadena compleja (Fetch → Analyze → Calculate → Report)
4. **Test 4**: Chain con traducción
5. **Test 5**: Manejo de errores

### Opción 3: Con AWS Bedrock + Claude Sonnet 4.5

```bash
# Configurar AWS primero
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_REGION="us-east-1"

# Instalar boto3
pip install boto3

# Ejecutar
cd /home/user/model-context-protocol
uv run python examples/bedrock_chain_demo/client_bedrock.py
```

Esto ejecutará 4 tests usando Claude via Bedrock para orquestar los chains.

### Opción 4: Ejecutar solo el servidor

```bash
cd /home/user/model-context-protocol
uv run python examples/bedrock_chain_demo/server.py
```

Luego puedes conectarte con cualquier cliente MCP.

## 🔗 Ejemplos de Chains

### Chain Simple: Fetch + Analyze

```json
{
  "method": "tools/chain",
  "params": {
    "chain": [
      {
        "tool": "fetch_user_data",
        "id": "user",
        "params": {"user_id": "user123"}
      },
      {
        "tool": "analyze_sentiment",
        "id": "sentiment",
        "params": {"text": "user.bio"}
      }
    ]
  }
}
```

### Chain Complejo: Full User Report

```json
{
  "method": "tools/chain",
  "params": {
    "chain": [
      {
        "tool": "fetch_user_data",
        "id": "user",
        "params": {"user_id": "user123"}
      },
      {
        "tool": "analyze_sentiment",
        "id": "sentiment",
        "params": {"text": "user.bio"},
        "onFailure": {"action": "skip_and_continue"}
      },
      {
        "tool": "calculate_metrics",
        "id": "metrics",
        "params": {"user_data": "user"}
      },
      {
        "tool": "format_report",
        "id": "report",
        "params": {
          "user_name": "user.name",
          "sentiment": "sentiment",
          "metrics": "metrics"
        }
      }
    ],
    "returnFormat": "final_only"
  }
}
```

## 📈 Output Esperado

Cuando ejecutes `client_bedrock.py`, verás:

```
====================================================================
MCP TOOL CHAINING DEMO - AWS BEDROCK CLIENT
====================================================================

🔌 Connecting to MCP server...
✅ Connected to: bedrock-chain-demo
   Protocol version: 2025-06-18
✅ Server supports tool chaining!

📦 Available tools: 6
   [✓] fetch_user_data: Fetch complete user profile data...
   [✓] analyze_sentiment: Analyze sentiment of text...
   [✓] translate_text: Translate text between languages
   [✓] generate_summary: Generate a concise summary...
   [✓] calculate_metrics: Calculate various metrics...
   [✓] format_report: Format various data into...

============================================================
TEST 1: Single Tool Call
============================================================
...

============================================================
TEST 2: Simple Tool Chain (Fetch → Analyze)
============================================================
...

============================================================
TEST 3: Complex Chain (Fetch → Analyze → Calculate → Report)
============================================================
...

📥 Chain Status: success
   Total steps: 4
   ✅ user: success (15.32ms)
   ✅ sentiment: success (8.45ms)
   ✅ metrics: success (3.21ms)
   ✅ report: success (5.67ms)

📄 Final Report:
# User Report: Alice Johnson

## Overview
Generated on: 2024-01-15 14:30:00

## Metrics
- Engagement Score: 39.0
- Activity Level: medium
- Follower Ratio: 0.75
- Total Posts: 3

## Sentiment Analysis
- Overall Sentiment: **positive**
- Confidence: 0.5
- Positive Score: 0.5
- Negative Score: 0.0

...

✅ ALL TESTS COMPLETED SUCCESSFULLY!
```

## 🎯 Beneficios Demostrados

1. **Reducción de Tokens**: Los datos intermedios (perfil de usuario) no pasan por el contexto del modelo
2. **Una sola RPC**: 4 pasos ejecutados con una sola llamada
3. **Validación Semántica**: El servidor valida esquemas antes de ejecutar
4. **Manejo de Errores**: Estrategias declarativas (skip_and_continue, abort, return_step)
5. **Transparencia**: Trace completo de ejecución con duración de cada paso

## 🐛 Troubleshooting

### Error: "AWS credentials not found"
```bash
# Configura tus credenciales
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
```

### Error: "Access denied to model"
- Verifica que tienes acceso al modelo en la consola de AWS Bedrock
- Región debe ser una que soporte Claude Sonnet 4.5

### Error: "Module mcp not found"
```bash
# Instala el SDK desde la raíz del proyecto
pip install -e .
```

### El servidor no responde
```bash
# Prueba ejecutar el servidor manualmente
python server.py

# Debería mostrar:
# ============================================================
# Starting MCP Server with Tool Chaining Support
# ============================================================
```

## 📚 Más Información

- [Documentación de Tool Chaining](../../docs/tool_chaining.md)
- [Propuesta Técnica](../../PROPOSAL.md)
- [Especificación MCP](https://modelcontextprotocol.io)

## 💡 Ideas para Extender

1. Agregar más herramientas (email, database, API calls)
2. Implementar chains condicionales complejos
3. Añadir métricas de rendimiento
4. Crear una interfaz web para visualizar chains
5. Implementar retry automático en fallos
