FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.12 "uvicorn[standard]==0.34.2" httpx==0.28.1 numpy==2.2.0 pandas==2.2.3 scikit-learn==1.5.2 xgboost==2.1.3
COPY ymc_next /app/ymc_next
RUN python -m unittest discover -s ymc_next -p 'test_*.py'
CMD ["sh","-c","exec uvicorn ymc_next.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
