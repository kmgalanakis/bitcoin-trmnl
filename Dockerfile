FROM python:3.12-alpine
WORKDIR /app
COPY requirements.txt .
# embit ships compiled secp256k1 libraries. Delete them so it uses its pure-Python code,
# because the Portainer server's CPU lacks x86-64-v2.
RUN pip install --no-cache-dir -r requirements.txt \
 && rm -rf "$(python -c 'import embit, os; print(os.path.dirname(embit.__file__))')/util/prebuilt"
COPY app.py test_app.py ./
EXPOSE 8091
CMD ["python", "-u", "app.py"]
