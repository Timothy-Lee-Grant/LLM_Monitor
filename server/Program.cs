//using Microsoft.AspNetCore.Builder;

namespace LLM_MONITOR.server; // do I need to wrap this??
public static class Program
{
    
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        var app = builder.Build();


        app.UseTelemetryMiddleware();

        app.UseAuthentication();
        app.UseAuthorization();

        app.MapControllers();

        app.Run();
    }
}