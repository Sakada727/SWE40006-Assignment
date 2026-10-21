# Production web server settings (used by the Dockerfile's CMD).
# Flask's built-in server is for development only, so the container runs gunicorn.

bind = "0.0.0.0:8080"
workers = 2   # two processes, suitable for a 1-2 vCPU EC2 instance
threads = 4   # each process serves several requests at once

# One JSON line per request on stdout, so `docker logs` and CloudWatch Logs both
# receive it. latency_ms is the request time in milliseconds, which a CloudWatch
# Logs metric filter can turn into an HTTP latency metric for the dashboard:
#   filter pattern  { $.latency_ms = * }   metric value  $.latency_ms
accesslog = "-"
errorlog = "-"
access_log_format = (
    '{"method":"%(m)s","path":"%(U)s","status":%(s)s,'
    '"bytes":%(B)s,"latency_ms":%(M)s,"remote":"%(h)s"}'
)
