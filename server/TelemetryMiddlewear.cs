
namespace LLM_MONITOR.server;
public class TelemetryMiddlewear 
{
    private readonly RequestDelegate _next;
    private ILogger<TelemetryMiddlewear> _logger;
    public TelemetryMiddlewear(RequestDelegate next, ILogger<TelemetryMiddlewear> logger)
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