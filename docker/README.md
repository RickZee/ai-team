# Docker

Build from **repository root**:

```bash
docker build -f docker/Dockerfile -t ai-team .
docker run -p 8501:8501 ai-team
```

Then open http://localhost:8501 for the Gradio UI.
