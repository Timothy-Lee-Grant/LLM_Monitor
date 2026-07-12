using System.Diagnostics;

namespace LLM_MONITOR.server;

public class TelemetryMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<TelemetryMiddleware> _logger;

    public TelemetryMiddleware(RequestDelegate next, ILogger<TelemetryMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        // Everything before `await _next(...)` runs on the way IN,
        // everything after runs on the way OUT (response already produced).
        var stopwatch = Stopwatch.StartNew();

        await _next(context);

        stopwatch.Stop();
        _logger.LogInformation(
            "telemetry method={Method} path={Path} status={StatusCode} elapsed_ms={ElapsedMs}",
            context.Request.Method,
            context.Request.Path,
            context.Response.StatusCode,
            stopwatch.ElapsedMilliseconds);

        // Future (roadmap): emit these as OpenTelemetry spans/metrics instead of
        // log lines, carrying a trace id that the langchain_service continues.
    }
}
