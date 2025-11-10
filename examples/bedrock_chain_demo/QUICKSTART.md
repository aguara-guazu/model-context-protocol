# Quick Start - Tool Chaining Demo

## 🚀 Prueba Rápida (30 segundos)

```bash
# Desde cualquier lugar
python examples/bedrock_chain_demo/simple_test.py
```

**Esto demostrará:**
- ✅ Chain de 2 pasos: fetch → analyze
- ✅ Chain de 4 pasos: fetch → analyze → calculate → report
- ✅ Resolución de referencias (`"step1.field"`)
- ✅ Generación de reportes completos

**No requiere dependencias extras!**

## 📊 Ver Resultados

Después de ejecutar, verás:

```
================================================================================
TOOL CHAINING DEMONSTRATION
================================================================================

TEST 1: Simple Chain (Fetch → Analyze)
[Step 1/2] fetch: fetch_user_data
  ✅ Success!
[Step 2/2] sentiment: analyze_sentiment
  ✅ Success!

🎯 FINAL OUTPUT:
  Sentiment: positive
  Confidence: 0.5

TEST 2: Complex Chain (Fetch → Analyze → Calculate → Report)
[Step 1/4] user: fetch_user_data
  ✅ Success!
[Step 2/4] sentiment: analyze_sentiment
  ✅ Success!
[Step 3/4] metrics: calculate_metrics
  ✅ Success!
[Step 4/4] report: format_report
  ✅ Success!

📄 GENERATED REPORT:
# User Report: Alice Johnson

## Sentiment Analysis
- Overall: positive
- Confidence: 0.5

## Metrics
- Engagement Score: 30.9
- Activity Level: medium

✅ DEMONSTRATION COMPLETE
```

## 🔧 Probar con MCP Real

Si quieres probar con el servidor MCP completo:

```bash
cd /home/user/model-context-protocol
uv run python examples/bedrock_chain_demo/manual_test.py
```

Esto ejecutará 5 tests diferentes contra el servidor MCP real.

## ☁️ Probar con AWS Bedrock + Claude

Si tienes AWS configurado:

```bash
# 1. Configurar AWS
export AWS_ACCESS_KEY_ID="tu_access_key"
export AWS_SECRET_ACCESS_KEY="tu_secret_key"
export AWS_REGION="us-east-1"

# 2. Instalar boto3
pip install boto3

# 3. Ejecutar
cd /home/user/model-context-protocol
uv run python examples/bedrock_chain_demo/client_bedrock.py
```

Esto hará que Claude Sonnet 4.5 orqueste los chains automáticamente.

## 📚 Más Información

- **README.md** - Documentación completa
- **DEMO_RESULTS.md** - Resultados de pruebas empíricas
- **server.py** - Código del servidor con 6 herramientas
- **../../docs/tool_chaining.md** - Documentación técnica

## ❓ Troubleshooting

### "ModuleNotFoundError: No module named 'mcp'"

**Solución:** Usa `simple_test.py` que no requiere mcp instalado:
```bash
python examples/bedrock_chain_demo/simple_test.py
```

O instala con uv:
```bash
cd /home/user/model-context-protocol
uv run python examples/bedrock_chain_demo/manual_test.py
```

### "AWS credentials not found"

**Solución:** Configura tus credenciales AWS:
```bash
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
```

## ✨ Lo Que Verás

1. **Resolución de Referencias**: `"step1.field"` se convierte en el valor real
2. **Ejecución Secuencial**: Cada paso usa outputs de pasos anteriores
3. **Datos Server-Side**: Datos intermedios nunca pasan por el modelo
4. **Reportes Complejos**: Generación de reportes desde múltiples fuentes

**¡Disfruta probando el tool chaining!** 🎉
