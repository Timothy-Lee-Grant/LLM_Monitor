// Retired from controllers/ during plan 001 Step 7 (2026_07_11): the gateway is now a YARP reverse proxy;
// controller-based forwarding (and its 4 bugs, see Stage 2 findings #7) is superseded. Reference only — excluded from compilation.

using Microsoft.AspNetCore.Mvc;
using System.Net;
using System.Threading.Tasks;

namespace LLM_MONITOR.server.controllers;

[ApiController]
[Route("/api/[controller]")]
public class TestController : ControllerBase
{
    [HttpGet]
    public async Task<IActionResult> MyTestGetEndpoint()
    {
        return Ok(new {Message="Hello from my test endpoint :D "});
    }

    [HttpPost]
    public async Task<IActionResult> MyTestPostEndpoint([FromBody] String requestData)
    {
        await Task.Delay(10);
        return Ok(new {status = "Received", data = requestData});
    }
}

// Commented-out practice block (serialization experiments, from-memory LlmChatCall attempt)
// moved to server/old_implementations/TestController_practice_notes.cs
