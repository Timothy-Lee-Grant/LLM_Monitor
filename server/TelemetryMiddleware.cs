
namespace LLM_MONITOR.server;
public class TelemetryMiddleware 
{
    private readonly RequestDelegate _next;
    private ILogger<TelemetryMiddleware> _logger;
    public TelemetryMiddleware(RequestDelegate next, ILogger<TelemetryMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        // Custom logging logic
        // ....

        await _next(context);

        // Custom exit logging
        // ....
    }
}