namespace LLM_MONITOR.server;

public static class Program
{
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        // YARP: routes/clusters live in appsettings.json ("ReverseProxy" section),
        // not in code. Config can be overridden per-environment with env vars using
        // double-underscore paths, e.g.:
        //   ReverseProxy__Clusters__langchain__Destinations__primary__Address
        builder.Services.AddReverseProxy()
            .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

        builder.Services.AddOpenApi();

        var app = builder.Build();

        if (app.Environment.IsDevelopment())
        {
            app.MapOpenApi();
        }

        // (Answering the old comment here: UseTelemetryMiddleware is an EXTENSION
        // METHOD — `this IApplicationBuilder builder` makes it callable *on* app.
        // It registers middleware into the request PIPELINE, not into DI. And no
        // `using` is needed because TelemetryMiddlewareExtention shares this file's
        // namespace, LLM_MONITOR.server.)
        //
        // Pipeline order is the architecture:
        //   telemetry -> [future: auth] -> [future: rate limiter] -> YARP forwarder
        app.UseTelemetryMiddleware();

        // Extension points (explicit non-goals for plan 001):
        // app.UseAuthentication();   // requires AddAuthentication(...) in services
        // app.UseAuthorization();
        // app.UseRateLimiter();      // requires AddRateLimiter(...) in services

        // The gateway's own liveness probe — everything else is proxied.
        app.MapGet("/healthz", () => Results.Ok(new { status = "ok" }));

        // Terminal step: anything matching a ReverseProxy route is forwarded
        // to the langchain_service cluster.
        app.MapReverseProxy();

        app.Run();
    }
}
