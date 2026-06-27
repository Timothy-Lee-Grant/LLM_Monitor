//using Microsoft.AspNetCore.Builder;

namespace LLM_MONITOR.server; // do I need to wrap this??
public static class Program
{
    
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        builder.Services.AddControllers();
        builder.Services.AddAuthentication(/* TODO: Find out what it means 'schema' */);
        builder.Services.AddAuthorization();

        var app = builder.Build();

        // TODO: Lack of understanding: I am invoking the method on app, but this method takes in a builder parameter and I think it is registering it with the DI service. But I don't quite know
        app.UseTelemetryMiddleware();

        app.UseAuthentication();
        app.UseAuthorization();

        app.MapControllers();

        app.Run();
    }
}