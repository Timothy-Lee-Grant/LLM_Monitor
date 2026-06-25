var builder = WebApplication.CreateBuilder(args);

// builder.Services.AddReverseProxy()
//     .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

var app = builder.Build();

app.Use(async (context, next) =>
{
    Console.WriteLine("Work that can write to the response. (1)");
    await next.Invoke(context);
    Console.WriteLine("Work that doesn't write to the response. (1)");
});

app.Use(async (context, next) =>
{
    Console.WriteLine("Work that can write to the response. (2)");
    await next.Invoke(context);
    Console.WriteLine("Work that doesn't write to the response. (2)");
});

app.Run(async context =>
{
    await context.Response.WriteAsync("Hello world!");
});

app.Use(async (context, next) =>
{
    Console.WriteLine("This statement isn't reached. (3)");
    await next.Invoke(context);
    Console.WriteLine("This statement isn't reached. (3)");
});

app.Run();