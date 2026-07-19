using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

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

        // ---- Observability (plan 002 Step 2) -------------------------------
        // Gated on OBSERVABILITY_ENABLED (set by build.sh --obs). When false,
        // nothing below registers: zero overhead, no exporter noise.
        var observabilityEnabled = builder.Configuration.GetValue<bool>("OBSERVABILITY_ENABLED");
        if (observabilityEnabled)
        {
            // Endpoint: standard OTEL env var wins, container-network default otherwise.
            var otlpEndpoint = new Uri(
                builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://otel-collector:4317");

            builder.Services.AddOpenTelemetry()
                // "gateway" is how our spans are labeled in Jaeger's service dropdown.
                .ConfigureResource(resource => resource.AddService(serviceName: "gateway"))
                .WithTracing(tracing => tracing
                    // Root span per inbound HTTP request:
                    .AddAspNetCoreInstrumentation()
                    // Child span per outbound HttpClient call — YARP forwards through
                    // HttpClient, so this is ALSO what injects the `traceparent` header
                    // on the proxied hop. That one header is the whole distributed-
                    // tracing trick (concepts doc 018 §Part 3).
                    .AddHttpClientInstrumentation()
                    // PUSH model: spans go to the collector, not straight to Jaeger.
                    .AddOtlpExporter(o => o.Endpoint = otlpEndpoint))
                .WithMetrics(metrics => metrics
                    .AddAspNetCoreInstrumentation()
                    .AddHttpClientInstrumentation()
                    // PULL model: this exporter just holds metrics in memory until
                    // Prometheus scrapes /metrics (mapped below).
                    .AddPrometheusExporter());
        }

        var app = builder.Build();

        if (observabilityEnabled)
        {
            app.MapPrometheusScrapingEndpoint(); // GET /metrics
        }

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
