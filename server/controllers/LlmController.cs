using Microsoft.AspNetCore.Mvc;
using System.Text.Json;
using System.ComponentModel.DataAnnotations;
using System.Net.Http;

namespace LLM_MONITOR.server.controllers;

[ApiController]
[Route("/api/[controller]")]
public class LlmController : ControllerBase
{
    private readonly IHttpClientFactory _httpClientFactory;

    LlmController(IHttpClientFactory httpClientFactory)
    {
        _httpClientFactory = httpClientFactory;
    }

    // We want an endpoint which allows the user to be able to send a POST request to us 
    // and that post request will have the message which the user wants to send to our llm
    
    [HttpPost]
    public async Task<IActionResult> SendChatMessage([FromBody] requestBodyDto requestBody)
    {
        // I think requestBody will be auto deserialized here, so I can act upon it as a object in C#

        // I now need to send another request to a different service
        // I need to create my own request and send it to the api endpoint.

        // The compiler was angry at me for this. I am keeping it for documentation purposes for now to illustrate a lack of understanding in my C# abilities
        // var bodyToLangchain = new 
        // {
        //     String UserMessage = requestBody.MessageToLlm;
        // };

        // Setup your outgoing payload for your Python service
        var outgoingPayload = new 
        {
            user = requestBody.UserName,
            prompt = requestBody.MessageToLlm
        };
        

        return Ok(JsonSerializer.Serialize( . ));
    }
    public class responseBodyDto
    {
        public string LlmResposeMessage { get; set; }
    }
    public class requestBodyDto
    {
        [Required(ErrorMessage = "UserName is required.")]
        public Guid? UserName { get; set; }

        [Required(ErrorMessage = "MessageToLlm is required")]
        [StringLength(2000, MinimumLength = 3, ErrorMessage = "Message must be between 3 and 2000 characters.")]
        public string MessageToLlm { get; set; }
    }
}
