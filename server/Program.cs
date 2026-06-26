//using Microsoft.AspNetCore.Builder;

namespace LLM_MONITOR.server; // do I need to wrap this??
public static class Program
{
    
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        // builder.Services.AddReverseProxy()
        //     .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

        var app = builder.Build();

        app.UseAuthentication();
        app.UseAuthorization();

        //app.UseMiddleware<TelemetryMiddlewear>();
        app.UseTelemetryMiddlewear();

        app.MapControllers();

        app.Run();
    }
}