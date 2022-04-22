FROM python:3.8-slim

COPY . /build

WORKDIR /build

RUN pip install --no-cache-dir .[telemetry,oidc]

WORKDIR /

ENTRYPOINT ["demo-app"]

CMD ["--metrics"]
