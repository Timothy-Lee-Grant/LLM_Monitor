





namespace LLM_MONITOR.server;

public static class TelemetryMiddlewearExtention
{
    public static IApplicationBuilder UseTelemetryMiddlewear(this IApplicationBuilder builder)
    {
        return builder.UseMiddleware<TelemetryMiddlewear>();
    }
}