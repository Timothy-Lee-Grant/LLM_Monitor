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

        // trace_id joins the LOG pillar to the TRACE pillar: grep this id in the
        // logs, paste it into Jaeger, land on the exact request's span tree.
        // Activity is .NET's built-in span representation; ASP.NET Core creates one
        // per request even without OTel (OTel exports it when enabled).
        var traceId = Activity.Current?.TraceId.ToString() ?? "none";

        _logger.LogInformation(
            "telemetry method={Method} path={Path} status={StatusCode} elapsed_ms={ElapsedMs} trace_id={TraceId}",
            context.Request.Method,
            context.Request.Path,
            context.Response.StatusCode,
            stopwatch.ElapsedMilliseconds,
            traceId);
    }
}
