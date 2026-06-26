





namespace LLM_MONITOR.server;

public static class TelemetryMiddlewareExtention
{
    public static IApplicationBuilder UseTelemetryMiddleware(this IApplicationBuilder builder)
    {
        return builder.UseMiddleware<TelemetryMiddleware>();
    }
}